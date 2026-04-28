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

# ── RRF / scoring constants ───────────────────────────────────────────────────
RRF_K = 60            # standard RRF constant
COS_FLOOR = 0.50      # minimum cosine for a chunk to be included in results
COS_ABSTAIN = 0.62    # if no result has cosine >= this AND no graph boost, abstain
                      # (tuned: nonsense queries top out ~0.60, real queries hit 0.65+)
COS_FLOOR_MIN = 3     # if fewer than this survive floor, take top-N regardless

# Path-prefix excludes — applied at query time because the FAISS index was
# built before these excludes were added. Any chunk whose path starts with
# one of these top-level folders is dropped from results.
PATH_EXCLUDE_PREFIXES = (
    "_archive/", "_Dupes/", "HarmonicInternal/", ".obsidian/", ".trash/",
)

# ── Graph rerank boost amounts ────────────────────────────────────────────────
GRAPH_BOOST_EXACT  = 0.50  # chunk source IS the queried entity
GRAPH_BOOST_1HOP   = 0.25  # source is 1 hop from entity
GRAPH_BOOST_2HOP   = 0.10  # source is 2 hops from entity
GRAPH_BOOST_MAX    = 0.60  # cap so no single entity drowns out high-cosine chunks


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
        "results": [],
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


def _rrf_fuse(
    vec_ranking: List[int],
    fts_ranking: List[int],
    k: int = RRF_K,
) -> List[Tuple[int, float]]:
    """
    Reciprocal Rank Fusion over two ranked lists.
    Returns list of (chunk_id, rrf_score) sorted descending.
    """
    scores: Dict[int, float] = {}
    for rank, rid in enumerate(vec_ranking):
        scores[rid] = scores.get(rid, 0.0) + 1.0 / (k + rank + 1)
    for rank, rid in enumerate(fts_ranking):
        scores[rid] = scores.get(rid, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: -x[1])


def _graph_boost(
    source_stem: str,
    entity_stems: List[str],
    graph: Any,
) -> float:
    """
    Given a chunk's source file stem and a list of entity stems from the query,
    return the maximum boost based on graph proximity.
    """
    if not entity_stems or graph is None:
        return 0.0

    best = 0.0
    for entity_stem in entity_stems:
        # Exact match
        if source_stem.lower() == entity_stem.lower():
            best = max(best, GRAPH_BOOST_EXACT)
            continue
        # Check graph proximity
        try:
            import networkx as nx
            ug = graph.to_undirected()
            # Find canonical node id for the entity stem
            entity_node = None
            for node_id in graph.nodes():
                if node_id.lower() == entity_stem.lower():
                    entity_node = node_id
                    break
                # first-token match (e.g. "Bella" → "Bella_Manchester")
                first = re.split(r"[_\s]+", node_id)[0].lower()
                if first == entity_stem.lower() and entity_node is None:
                    entity_node = node_id

            if entity_node is None:
                continue

            # Find the source node
            source_node = None
            for node_id in graph.nodes():
                if node_id.lower() == source_stem.lower():
                    source_node = node_id
                    break

            if source_node is None:
                continue

            # Shortest path distance
            try:
                dist = nx.shortest_path_length(ug, entity_node, source_node)
                if dist == 1:
                    best = max(best, GRAPH_BOOST_1HOP)
                elif dist == 2:
                    best = max(best, GRAPH_BOOST_2HOP)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                pass
        except Exception:
            pass

    return min(best, GRAPH_BOOST_MAX)


def hybrid(q: str, _graph: Any = None) -> Dict[str, Any]:
    glossary_hit = _lookup_glossary(q)
    if glossary_hit:
        return glossary_hit

    # Vector search — returns (ids, cosine_sims) since index is IndexFlatIP + L2-norm
    vids, vsims = vec_ids(q, FAST_TOPK)

    # Build a cosine map: chunk_id → cosine score (real [-1, 1])
    cosine_map: Dict[int, float] = {}
    for rid, sim in zip(vids, vsims):
        cosine_map[rid] = round(float(sim), 4)

    # FTS search
    fids = fts_ids(q, FAST_TOPK)

    # RRF fusion (replaces weighted-sum mixing)
    rrf_ranked = _rrf_fuse(vids, fids, k=RRF_K)

    # Map chunk_id → rrf_score
    rrf_map: Dict[int, float] = {rid: score for rid, score in rrf_ranked}

    # All candidate IDs in RRF order
    candidate_ids = [rid for rid, _ in rrf_ranked][: FAST_TOPK * 2]

    # ── Entity-graph rerank ───────────────────────────────────────────────────
    # Detect entities in query
    entity_stems: List[str] = []
    graph = _graph
    if graph is None:
        try:
            from .entity_graph import get_graph
            graph = get_graph()
        except Exception:
            graph = None

    if graph is not None:
        try:
            from .entity_detector import detect_entities, load_entity_names
            entity_names = load_entity_names(graph)
            entity_node_ids = detect_entities(q, entity_names)
            # Convert node IDs to stems (the node_id IS the stem)
            entity_stems = entity_node_ids
        except Exception:
            entity_stems = []

    # Load metadata for all candidates
    meta = _load_meta(candidate_ids)

    # Compute adjusted scores: rrf_score + graph_boost
    adjusted: List[Tuple[float, float, float, int]] = []  # (adj_score, rrf, boost, rid)
    for rid in candidate_ids:
        rrf = rrf_map.get(rid, 0.0)
        boost = 0.0
        if entity_stems:
            m = meta.get(str(rid), {})
            path = m.get("path") or ""
            if path:
                source_stem = Path(path).stem
                boost = _graph_boost(source_stem, entity_stems, graph)
        adj = rrf + boost
        adjusted.append((adj, rrf, boost, rid))

    adjusted.sort(key=lambda x: -x[0])

    # Apply COS_FLOOR: keep only chunks with cosine >= floor
    # For FTS-only chunks (no cosine), treat as passing the floor
    above_floor = [
        (adj, rrf, boost, rid)
        for adj, rrf, boost, rid in adjusted
        if cosine_map.get(rid, COS_FLOOR) >= COS_FLOOR
    ]

    # If too few survive, fall back to top COS_FLOOR_MIN regardless
    if len(above_floor) < COS_FLOOR_MIN:
        above_floor = adjusted[:COS_FLOOR_MIN]

    # Truncate to FAST_TOPK
    final_ranked = above_floor[:FAST_TOPK]

    # Apply optional focus-term boosts from settings + recency boost
    temporal_intent = _has_temporal_intent(q)
    try:
        app_dir = settings_cache.APP_DIR
        cfg_path = (app_dir / "settings.json") if app_dir else None
        s = settings_cache.load_settings(cfg_path, ttl=2)
        if isinstance(s, dict) and "settings" in s:
            s = s["settings"]
        boosts_enabled = bool(s.get("BOOSTS_ENABLED", False))
        focus_terms = [str(t).lower() for t in (s.get("FOCUS_TERMS") or [])]

        now_ts = time.time() if temporal_intent else 0.0

        def _combined_sort_key(item: Tuple) -> Tuple[float, str]:
            adj, rrf, boost, rid = item
            m = meta.get(str(rid), {})
            path = str(m.get("path", "")).lower()
            extra = 0.0
            if boosts_enabled and focus_terms and any(t in path for t in focus_terms):
                extra -= 1.0
            if temporal_intent:
                extra += _recency_adjustment(m.get("mtime"), now_ts)
            return (-(adj + extra), path)

        final_ranked = sorted(final_ranked, key=_combined_sort_key)

        if temporal_intent:
            boosted = sum(
                1
                for _, _, _, rid in final_ranked
                if _recency_adjustment(meta.get(str(rid), {}).get("mtime"), now_ts) < -0.1
            )
            log.info(
                "Temporal intent detected in query %r — recency boost applied to %d/%d chunks",
                q[:80],
                boosted,
                len(final_ranked),
            )
    except Exception as e:
        log.debug("Boost/ranking layer skipped: %s", e)

    # Build result items and snippets
    snippets: List[str] = []
    cits: List[str] = []
    results: List[Dict[str, Any]] = []

    for adj, rrf, boost, rid in final_ranked:
        m = meta.get(str(rid))
        if not m:
            continue
        path = m.get("path") or "unknown"
        # Drop chunks whose path starts with an excluded top-level folder.
        # FAISS index pre-dates the exclude policy so we filter here.
        if any(path.startswith(pfx) for pfx in PATH_EXCLUDE_PREFIXES):
            continue
        title = (m.get("title") or "").strip() or path.split("/")[-1]
        text = (m.get("text") or "").strip()
        cosine = cosine_map.get(rid)

        result_item: Dict[str, Any] = {
            "source": title,
            "path": path,
            "cosine": round(cosine, 4) if cosine is not None else None,
            "rrf_score": round(rrf, 6),
            "graph_boost": round(boost, 4),
            "adj_score": round(adj, 6),
        }
        results.append(result_item)

        if text:
            snippets.append(f"[{title} > …]\n{text[:1500]}")
        cits.append(f"{title} ({path})")

    context = ("\n\n---\n\n").join(snippets) if snippets else ""

    # Best cosine among semantic candidates
    top_cosine = max(vsims) if vsims else 0.0

    return {
        "question": q,
        "context": context,
        "citations": cits[:5],
        "results": results,
        "retrieval": {
            "topk": FAST_TOPK,
            "vec_ids": vids,
            "vec_topcos": round(float(top_cosine), 4),
            "fts_ids": fids,
            "fused": len(final_ranked),
            "cos_floor": COS_FLOOR,
            "entities_detected": entity_stems,
        },
        # Fast path can abstain if we didn't retrieve anything useful.
        # "Useful" = (a) at least one chunk with cosine >= COS_ABSTAIN, OR
        # (b) at least one chunk with a non-zero graph_boost (entity detected and connected).
        "abstain_hint": (
            not bool(context)
            or (
                not any((r.get("cosine") or 0.0) >= COS_ABSTAIN for r in results)
                and not any((r.get("graph_boost") or 0.0) > 0.0 for r in results)
            )
        ),
    }
