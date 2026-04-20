from __future__ import annotations

import difflib
import logging
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

log = logging.getLogger(__name__)

# ── Recency-aware retrieval ───────────────────────────────────────────────────
# When a query expresses temporal intent ("latest status", "most recent", etc.)
# we boost newer chunks so supersession-sensitive queries prefer current facts.
TEMPORAL_QUERY_KEYWORDS = (
    "latest", "current", "currently", "recent", "recently",
    "right now", "today", "this week", "this month",
    "most recent", "up to date", "up-to-date", "newest",
    "status of", "status on", "where are we with", "where do we stand",
)

# Tunable: how strong the recency signal is vs. semantic/FTS rank.
# Values chosen so a ~30-day-old chunk beats a semantically-similar 1-year-old.
RECENCY_WEIGHT = 3.0          # scaling factor for the recency rank adjustment
RECENCY_HALFLIFE_DAYS = 30.0  # chunks this old get ~half the max boost
RECENCY_FLOOR_DAYS = 365.0    # chunks older than this get zero boost


def _has_temporal_intent(query: str) -> bool:
    """Detect whether a query expresses recency/supersession intent."""
    if not query:
        return False
    q = query.lower()
    return any(kw in q for kw in TEMPORAL_QUERY_KEYWORDS)


def _recency_adjustment(mtime_value: Any, now_ts: float) -> float:
    """
    Return a NEGATIVE number proportional to recency, so that sorting ascending
    places newer chunks earlier. Returns 0.0 for chunks older than RECENCY_FLOOR_DAYS
    or when mtime is missing/unparseable.
    """
    if mtime_value is None:
        return 0.0
    try:
        mt = float(mtime_value)
    except (TypeError, ValueError):
        return 0.0
    if mt <= 0:
        return 0.0
    age_days = max(0.0, (now_ts - mt) / 86400.0)
    if age_days >= RECENCY_FLOOR_DAYS:
        return 0.0
    # Exponential decay: newest chunks get the largest negative adjustment
    import math
    decay = math.exp(-age_days / RECENCY_HALFLIFE_DAYS)
    return -RECENCY_WEIGHT * decay

try:  # test-friendly imports
    from retrieval.store import embed_query, get_hnsw  # type: ignore
except Exception:  # pragma: no cover
    from ..embedder_provider import embed_query  # type: ignore
    from .store import get_hnsw  # type: ignore
try:
    from ...config import META_CSV_PATH  # type: ignore
except Exception:  # pragma: no cover
    from ..config import META_CSV_PATH  # type: ignore
import sqlite3

from ...settings_cache import settings_cache
from .db import get_sqlite_ro

# Keep existing knobs/shape
FAST_TOPK = 12
COS_FLOOR = 0.30

GLOSSARY_PATH = Path(__file__).resolve().parents[4] / "Vault" / "System" / "glossary.md"

GlossaryEntry = Tuple[str, str, str]


def _normalize_text(value: str) -> str:
    return re.sub(r"[^0-9a-z]+", " ", (value or "").lower()).strip()


@lru_cache(maxsize=1)
def _load_glossary_terms() -> List[GlossaryEntry]:
    entries: List[GlossaryEntry] = []
    try:
        text = GLOSSARY_PATH.read_text(encoding="utf-8")
    except Exception:
        return entries

    blocks = re.split(r"^---\s*$", text, flags=re.MULTILINE)
    for block in blocks:
        term_match = re.search(r"^##\s*-\s*(.+)$", block, flags=re.MULTILINE)
        if not term_match:
            continue
        term = term_match.group(1).strip()
        if not term:
            continue

        def_match = re.search(r"\*\*Definition.*?\*\*:\s*(.+)", block)
        short_match = re.search(r"\*\*Short Description\*\*:\s*(.+)", block)
        definition = ""
        if def_match:
            definition = def_match.group(1).strip()
        elif short_match:
            definition = short_match.group(1).strip()
        else:
            fallback_lines = [
                ln.strip()
                for ln in block.splitlines()
                if ln.strip() and not ln.strip().startswith("##")
            ]
            if fallback_lines:
                definition = fallback_lines[0]

        definition = definition.strip()
        if not definition:
            continue

        entries.append((term, _normalize_text(term), definition))

    return entries


def _build_glossary_response(query: str, term: str, definition: str) -> Dict[str, Any]:
    snippet = f"**{term}**\n{definition}"
    return {
        "question": query,
        "context": snippet,
        "citations": [f"{term} (glossary)"],
        "retrieval": {
            "topk": 1,
            "vec_ids": [],
            "vec_topcos": 0.0,
            "fts_ids": [],
            "fused": 0,
            "cos_floor": COS_FLOOR,
        },
        "abstain_hint": False,
    }


def _lookup_glossary(query: str) -> Dict[str, Any] | None:
    entries = _load_glossary_terms()
    if not entries:
        return None

    q_norm = _normalize_text(query)
    if not q_norm:
        return None

    entries_by_norm = {norm: (term, definition) for term, norm, definition in entries if norm}
    match = entries_by_norm.get(q_norm)
    if match:
        term, definition = match
        return _build_glossary_response(query, term, definition)

    padded_query = f" {q_norm} "
    for term, norm, definition in entries:
        if norm and f" {norm} " in padded_query:
            return _build_glossary_response(query, term, definition)

    normalized_terms = [norm for _, norm, _ in entries if norm]
    close: List[str] = []
    if normalized_terms:
        close = difflib.get_close_matches(q_norm, normalized_terms, n=1, cutoff=0.8)
        if not close:
            for token in q_norm.split():
                close = difflib.get_close_matches(token, normalized_terms, n=1, cutoff=0.9)
                if close:
                    break

    if close:
        target = close[0]
        for term, norm, definition in entries:
            if norm == target:
                return _build_glossary_response(query, term, definition)

    return None


def _load_meta(ids: List[int]) -> Dict[str, Dict[str, Any]]:
    """
    Return metadata for the given chunk IDs.
    Prefers CSV (meta.csv with 'id' or 'chunk_rowid' column), then falls back to DB join.
    """
    out: Dict[str, Dict[str, Any]] = {}
    if not ids:
        return out

    id_set = {str(i) for i in ids}

    # 1) CSV first (fast path and avoids DB schema variance)
    try:
        import csv

        with META_CSV_PATH.open("r", newline="", encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for row in rdr:
                rid = row.get("id") or row.get("chunk_rowid")
                if rid and rid in id_set:
                    txt = row.get("text") or ""
                    row["token_est"] = row.get("token_est") or max(1, len(txt) // 4)
                    out[str(rid)] = row
        if out:
            return out
    except Exception:
        pass

    # 2) Fallback: join chunks/documents in SQLite
    try:
        from .db import get_sqlite_ro

        con = get_sqlite_ro()
        placeholders = ",".join("?" * len(ids))
        q = (
            "SELECT c.id AS chunk_rowid, d.path, d.title, "
            "       c.heading_path AS heading, c.text, c.mtime, c.token_est "
            "FROM chunks c JOIN documents d ON d.id = c.doc_id "
            f"WHERE c.id IN ({placeholders})"
        )
        rows = con.execute(q, ids).fetchall()
        for r in rows:
            d = dict(r)
            d["token_est"] = d.get("token_est") or max(1, len((d.get("text") or "")) // 4)
            out[str(int(d["chunk_rowid"]))] = d
    except Exception:
        pass

    return out


# Tokenize and build an FTS5 MATCH expression like: token* OR token* ...
_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


def _fts_build_query(text: str) -> str:
    """
    Build an FTS5 MATCH query like: token* OR token* OR ...
    Using wildcards avoids exact-phrase-only misses.
    """
    tokens = [t.lower() for t in _WORD_RE.findall(text or "")]
    tokens = [t for t in tokens if len(t) >= 3]  # drop tiny tokens
    if not tokens:
        return ""  # signal: nothing to search
    return " OR ".join(f"{t}*" for t in tokens)


def fts_ids(q: str, topk: int) -> list[int]:
    con = get_sqlite_ro()
    query = _fts_build_query(q)
    if not query:
        return []

    # Try with bm25(), then without (some SQLite builds omit bm25)
    sql_try = [
        f"SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH {query!r} "
        f"ORDER BY bm25(chunks_fts) LIMIT {int(topk)}",
        f"SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH {query!r} LIMIT {int(topk)}",
    ]
    for sql in sql_try:
        try:
            return [r[0] for r in con.execute(sql).fetchall()]
        except sqlite3.OperationalError:
            continue

    # FINAL FALLBACK: plain LIKE on base table if FTS is stubborn
    try:
        like_q = f"%{q}%"
        rows = con.execute(
            "SELECT rowid FROM chunks WHERE text LIKE ? LIMIT ?",
            (like_q, int(topk)),
        ).fetchall()
        ids = [r[0] for r in rows]
        if ids:
            return ids
    except Exception:
        pass

    # Fuzzy fallback: scan a limited candidate set by LIKE on first token, then rank
    try:
        tokens = [t for t in _WORD_RE.findall(q.lower()) if len(t) >= 3]
        if not tokens:
            return []
        like = f"%{tokens[0]}%"
        rows = con.execute(
            "SELECT rowid, substr(text,1,1000) FROM chunks WHERE text LIKE ? LIMIT 500",
            (like,),
        ).fetchall()
        scored: List[Tuple[float, int]] = []
        for rid, snippet in rows:
            try:
                s = snippet or ""
                score = difflib.SequenceMatcher(None, q.lower(), s.lower()).ratio()
                if score >= 0.5:
                    scored.append((score, int(rid)))
            except Exception:
                continue
        scored.sort(reverse=True)
        return [rid for _score, rid in scored[:topk]]
    except Exception:
        return []


def vec_ids(q: str, topk: int) -> Tuple[List[int], List[float]]:
    index = get_hnsw()
    if index is None:
        return [], []
    qv = np.asarray([embed_query(q)], dtype="float32")
    if qv.size == 0 or qv.shape[1] == 0:
        return [], []
    # FAISS index.search() returns (sims, ids) in that order
    sims, ids = index.search(qv, topk)
    return [int(x) for x in ids[0].tolist()], [float(x) for x in sims[0].tolist()]


def hybrid(q: str) -> Dict[str, Any]:
    glossary_hit = _lookup_glossary(q)
    if glossary_hit:
        return glossary_hit

    # Vector search
    vids, vsims = vec_ids(q, FAST_TOPK)

    # FTS search
    fids = fts_ids(q, FAST_TOPK)

    # Fuse (order-preserving union)
    fused = list(dict.fromkeys(vids + fids))[: FAST_TOPK * 2]

    # Apply optional focus-term boosts from settings (hot‑reloadable)
    # AND recency boost when the query expresses temporal intent.
    temporal_intent = _has_temporal_intent(q)
    try:
        app_dir = settings_cache.APP_DIR
        cfg_path = (app_dir / "settings.json") if app_dir else None
        s = settings_cache.load_settings(cfg_path, ttl=2)
        if isinstance(s, dict) and "settings" in s:
            s = s["settings"]
        boosts_enabled = bool(s.get("BOOSTS_ENABLED", False))
        focus_terms = [str(t).lower() for t in (s.get("FOCUS_TERMS") or [])]
        meta_for_boost = _load_meta(fused)

        now_ts = time.time() if temporal_intent else 0.0

        def _combined_sort_key(rid: int) -> Tuple[float, str]:
            m = meta_for_boost.get(str(rid), {})
            path = str(m.get("path", "")).lower()
            score = 0.0
            # Focus-term boost (existing behaviour)
            if boosts_enabled and focus_terms and any(t in path for t in focus_terms):
                score -= 1.0
            # Recency boost (new — only when query is temporal)
            if temporal_intent:
                score += _recency_adjustment(m.get("mtime"), now_ts)
            return (score, path)  # path as secondary key for determinism

        fused = sorted(fused, key=_combined_sort_key)

        if temporal_intent:
            boosted = sum(
                1
                for rid in fused
                if _recency_adjustment(meta_for_boost.get(str(rid), {}).get("mtime"), now_ts) < -0.1
            )
            log.info(
                "Temporal intent detected in query %r — recency boost applied to %d/%d chunks",
                q[:80],
                boosted,
                len(fused),
            )
    except Exception as e:
        log.debug("Boost/ranking layer skipped: %s", e)

    # Metadata & snippets
    meta = _load_meta(fused)
    snippets: List[str] = []
    cits: List[str] = []

    for rid in fused[: min(len(fused), FAST_TOPK)]:
        m = meta.get(str(rid))
        if not m:
            continue
        title = (m.get("title") or "").strip() or (m.get("path") or "").split("/")[-1]
        path = m.get("path") or "unknown"
        text = (m.get("text") or "").strip()
        if text:
            snippets.append(f"[{title} > …]\n{text[:1500]}")
        # Always include citation to support tests with empty text
        cits.append(f"{title} ({path})")

    context = ("\n\n---\n\n").join(snippets) if snippets else ""

    return {
        "question": q,
        "context": context,
        "citations": cits[:5],
        "retrieval": {
            "topk": FAST_TOPK,
            "vec_ids": vids,
            "vec_topcos": min(vsims) if vsims else 0.0,
            "fts_ids": fids,
            "fused": len(fused),
            "cos_floor": COS_FLOOR,
        },
        # Fast path can abstain if we didn't retrieve anything useful
        "abstain_hint": (not bool(context)),
    }
