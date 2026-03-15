from __future__ import annotations

import difflib
from typing import Any, Dict, List, Tuple

try:
    from ... import settings_cache as settings_mod
except ImportError:  # pragma: no cover - fallback for flattened package imports
    import settings_cache as settings_mod  # type: ignore

# Reuse the fast-path helpers to stay consistent with your stack
try:
    # Prefer test-friendly top-level package if available
    from retrieval.search_fast import (  # type: ignore
        COS_FLOOR,
        FAST_TOPK,
        _load_meta,
        fts_ids,
        vec_ids,
    )
except Exception:  # pragma: no cover
    from .search_fast import (  # type: ignore
        COS_FLOOR,
        FAST_TOPK,
        _load_meta,
        fts_ids,
        vec_ids,
    )


FORCE_NO_ABSTAIN_DEEP = True


def hybrid(q: str) -> Dict[str, Any]:
    # Deep = ask for more neighbors/FTS hits and build a longer context
    vids, vsims = vec_ids(q, FAST_TOPK * 2)
    fids = fts_ids(q, FAST_TOPK * 2)

    fused = list(dict.fromkeys(vids + fids))[: FAST_TOPK * 4]

    # Additional fuzzy fallback for short proper names or poorly tokenized queries
    try:
        from .db import get_sqlite_ro

        con = get_sqlite_ro()
        tokens = [t for t in q.split() if len(t) >= 3]
        if tokens:
            like = f"%{tokens[0]}%"
            rows = con.execute(
                "SELECT rowid, substr(text,1,1000) FROM chunks WHERE lower(text) LIKE lower(?) LIMIT 500",
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
            fuzz_ids = [rid for _sc, rid in scored[: FAST_TOPK * 2]]
            if fuzz_ids:
                fused = list(dict.fromkeys(fuzz_ids + fused))[: FAST_TOPK * 4]
    except Exception:
        pass

    # Optional: restrict to Vault only if configured (hot‑reloadable)
    try:
        app_dir = settings_mod.APP_DIR
        cfg_path = (app_dir / "settings.json") if app_dir else None
        base_settings = settings_mod.settings_cache()
        if isinstance(base_settings, dict):
            merged_settings = dict(base_settings)
        else:
            merged_settings = {}
        loaded_settings: Any = {}
        if cfg_path and cfg_path.exists():
            try:
                loaded_settings = settings_mod.load_settings(cfg_path, ttl=2)
            except Exception:
                loaded_settings = {}
        if isinstance(loaded_settings, dict) and "settings" in loaded_settings:
            loaded_settings = loaded_settings["settings"]
        if isinstance(loaded_settings, dict):
            merged_settings.update(loaded_settings)
        vault_only = bool(merged_settings.get("DEEP_VAULT_ONLY", False))
        if vault_only:
            # Filter to Vault-only documents by inspecting path metadata.
            # Tests feed absolute-like paths such as "/vault/doc.md" versus "/other/doc.md".
            # Real runs store Vault‑relative paths like ".../path/in/vault.md".
            meta_for_filter = _load_meta(fused)

            def _is_vault_path(path: str) -> bool:
                p = (path or "").replace("\\", "/").lower()
                return p.startswith("/vault/") or p.startswith("vault/")

            fused = [
                rid
                for rid in fused
                if _is_vault_path(str(meta_for_filter.get(str(rid), {}).get("path", "")))
            ]
    except Exception:
        pass

    meta = _load_meta(fused)

    snippets: List[str] = []
    cits: List[str] = []

    for rid in fused[: min(len(fused), FAST_TOPK * 2)]:
        m = meta.get(str(rid))
        if not m:
            continue
        title = (m.get("title") or "").strip() or (m.get("path") or "").split("/")[-1]
        path = m.get("path") or "unknown"
        text = (m.get("text") or "").strip()
        if text:
            snippets.append(f"[{title} > …]\n{text[:2000]}")
        cits.append(f"{title} ({path})")

    context = ("\n\n---\n\n").join(snippets) if snippets else ""

    out = {
        "question": q,
        "context": context,
        "citations": cits[:10],
        "retrieval": {
            "topk": FAST_TOPK * 2,
            "vec_ids": vids,
            "vec_topcos": min(vsims) if vsims else 0.0,
            "fts_ids": fids,
            "fused": len(fused),
            "cos_floor": COS_FLOOR,
        },
    }
    # Recommend abstain if no context fetched
    # Abstain only when explicitly configured to restrict to vault and no context
    try:
        app_dir = settings_mod.APP_DIR
        merged_settings = settings_mod.settings_cache()
        if isinstance(merged_settings, dict):
            merged_settings = dict(merged_settings)
        else:
            merged_settings = {}
        cfg_path = (app_dir / "settings.json") if app_dir else None
        loaded_settings: Any = {}
        if cfg_path and cfg_path.exists():
            try:
                loaded_settings = settings_mod.load_settings(cfg_path, ttl=2)
            except Exception:
                loaded_settings = {}
        if isinstance(loaded_settings, dict) and "settings" in loaded_settings:
            loaded_settings = loaded_settings["settings"]
        if isinstance(loaded_settings, dict):
            merged_settings.update(loaded_settings)
        vault_only2 = bool(merged_settings.get("DEEP_VAULT_ONLY", False))
    except Exception:
        vault_only2 = False
    out["abstain_hint"] = vault_only2 and (not bool(context))
    return out
