from __future__ import annotations

import fnmatch
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, List, Optional

import faiss
import numpy as np
import pandas as pd

from ..config import HNSW_PATH, META_CSV_PATH
from ..embedder_provider import get_embedder

try:
    from ..index.config import EXCLUDE_GLOBS  # type: ignore
except Exception:
    EXCLUDE_GLOBS: list[str] = []
from .store import get_sqlite_rw, rebuild_chunks_from_vault

PROGRESS_EVERY = 16  # Reduced: batch operations timeout at 64; smaller batches more reliable


def _load_last_index_ts(path: Path) -> float:
    try:
        return float(json.loads(path.read_text()).get("timestamp", 0))
    except Exception:
        return 0.0


def _write_last_index_ts(path: Path) -> None:
    path.write_text(json.dumps({"timestamp": time.time()}))


def reindex(
    progress_cb: Optional[Callable[[str, Any], None]] = None,
    incremental: bool = False,
    build_id: str | None = None,
):
    def _notify(phase: str, **metrics: Any) -> None:
        if progress_cb:
            try:
                progress_cb(phase, **metrics)
            except Exception:
                pass

    if build_id:
        _notify("start", build_id=build_id)

    ts_path = Path(".rag_last_index.json")
    if incremental:
        last_ts = _load_last_index_ts(ts_path)
        vault_dir = Path(os.getenv("VAULT_DIR", "Vault"))
        changed: List[Path] = []
        if vault_dir.exists():
            for p in vault_dir.rglob("*"):
                if not p.is_file():
                    continue
                rel = p.relative_to(vault_dir).as_posix()
                if any(fnmatch.fnmatch(rel, g) for g in EXCLUDE_GLOBS):
                    continue
                try:
                    if p.stat().st_mtime > last_ts:
                        changed.append(p)
                except OSError:
                    continue
        if not changed:
            _write_last_index_ts(ts_path)
            return
        rebuild_chunks_from_vault([str(p) for p in changed])

        con = get_sqlite_rw()
        placeholders = ",".join(["?"] * len(changed))
        rows = con.execute(
            "SELECT c.id AS chunk_rowid, d.path, d.title, c.heading_path AS heading, c.text, c.mtime "
            f"FROM chunks c JOIN documents d ON d.id = c.doc_id WHERE d.path IN ({placeholders}) ORDER BY c.id",
            [str(p) for p in changed],
        ).fetchall()
        ids = [int(r["chunk_rowid"]) for r in rows]
        texts = [r["text"] or "" for r in rows]

        provider = get_embedder()
        try:
            _, dim = provider
        except Exception:
            dim = provider.get_sentence_embedding_dimension() or 768

        if HNSW_PATH.exists():
            index = faiss.read_index(str(HNSW_PATH))
            try:
                remove_ids = faiss.IDSelectorBatch(np.array(ids, dtype="int64"))
                index.remove_ids(remove_ids)
            except Exception:
                pass
        else:
            index = faiss.IndexIDMap2(faiss.IndexFlatIP(dim))

        batch = PROGRESS_EVERY
        for i in range(0, len(texts), batch):
            sub = texts[i : i + batch]
            sub_ids = ids[i : i + len(sub)]
            raw_vecs = provider.encode(sub)
            # Filter out failed embeddings (empty lists from Ollama errors)
            valid = [(v, sid) for v, sid in zip(raw_vecs, sub_ids) if v and len(v) > 0]
            if not valid:
                continue
            vecs_ok, ids_ok = zip(*valid)
            vecs = np.asarray(vecs_ok, dtype="float32")
            faiss.normalize_L2(vecs)
            id_batch = np.array(ids_ok, dtype="int64")
            index.add_with_ids(vecs, id_batch)

        faiss.write_index(index, str(HNSW_PATH))

        meta_rows = [
            [
                r["chunk_rowid"],
                r["path"],
                r["title"],
                r["heading"],
                r["text"] or "",
                r["mtime"],
                max(1, len((r["text"] or "")) // 4),
            ]
            for r in rows
        ]
        new_df = pd.DataFrame(
            meta_rows,
            columns=["chunk_rowid", "path", "title", "heading", "text", "mtime", "token_est"],
        )
        new_df.insert(0, "id", new_df["chunk_rowid"])

        if META_CSV_PATH.exists():
            old_df = pd.read_csv(META_CSV_PATH)
            old_df = old_df[~old_df["chunk_rowid"].isin(new_df["chunk_rowid"])]
            df = pd.concat([old_df, new_df], ignore_index=True)
        else:
            df = new_df
        META_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(META_CSV_PATH, index=False)
        _write_last_index_ts(ts_path)

        total_chunks = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        written = index.ntotal
        ok = total_chunks == written
        _notify("verify", expected=total_chunks, written=written, ok=ok)
        if not ok:
            raise RuntimeError(
                f"vector_index.count_mismatch expected={total_chunks} written={written}"
            )
        _notify("final", status="ok")
        return

    # Full reindex path
    rebuild_chunks_from_vault()

    con = get_sqlite_rw()
    rows = con.execute(
        "SELECT c.id AS chunk_rowid, d.path, d.title, c.heading_path AS heading, c.text, c.mtime "
        "FROM chunks c JOIN documents d ON d.id = c.doc_id ORDER BY c.id"
    ).fetchall()
    ids = [int(r["chunk_rowid"]) for r in rows]
    texts = [r["text"] or "" for r in rows]

    provider = get_embedder()
    try:
        _, dim = provider
    except Exception:
        dim = provider.get_sentence_embedding_dimension() or 768

    index = faiss.IndexIDMap2(faiss.IndexFlatIP(dim))

    import logging as _log
    _logger = _log.getLogger("indexer")
    batch = PROGRESS_EVERY
    total_batches = (len(texts) + batch - 1) // batch
    skipped = 0
    for i in range(0, len(texts), batch):
        sub = texts[i : i + batch]
        sub_ids = ids[i : i + len(sub)]
        raw_vecs = provider.encode(sub)
        # Filter out failed embeddings (empty lists from Ollama errors)
        valid = [(v, sid) for v, sid in zip(raw_vecs, sub_ids) if v and len(v) > 0]
        if not valid:
            skipped += len(sub)
            continue
        skipped += len(sub) - len(valid)
        vecs_ok, ids_ok = zip(*valid)
        vecs = np.asarray(vecs_ok, dtype="float32")
        faiss.normalize_L2(vecs)
        id_batch = np.array(ids_ok, dtype="int64")
        index.add_with_ids(vecs, id_batch)
        batch_num = i // PROGRESS_EVERY + 1
        if batch_num % 50 == 0 or batch_num == total_batches:
            print(f"  [embed] batch {batch_num}/{total_batches} | indexed={index.ntotal} skipped={skipped}", flush=True)

    print(f"  [embed] complete: indexed={index.ntotal} skipped={skipped} total={len(texts)}", flush=True)
    faiss.write_index(index, str(HNSW_PATH))

    meta_rows = [
        [
            r["chunk_rowid"],
            r["path"],
            r["title"],
            r["heading"],
            r["text"] or "",
            r["mtime"],
            max(1, len((r["text"] or "")) // 4),
        ]
        for r in rows
    ]
    df = pd.DataFrame(
        meta_rows,
        columns=["chunk_rowid", "path", "title", "heading", "text", "mtime", "token_est"],
    )
    df.insert(0, "id", df["chunk_rowid"])
    META_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(META_CSV_PATH, index=False)
    _write_last_index_ts(ts_path)

    total_chunks = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    written = index.ntotal
    ok = written > 0 and written >= (total_chunks * 0.95)  # allow up to 5% embed failures
    _notify("verify", expected=total_chunks, written=written, ok=ok)
    if not ok:
        import logging as _logging
        _logging.getLogger("indexer").warning(
            "vector_index.count_mismatch expected=%d written=%d", total_chunks, written
        )
    _notify("final", status="ok")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RAG indexer — rebuild or incrementally update the FAISS vector index")
    parser.add_argument("--incremental", action="store_true", help="Only re-index files changed since last run (uses .rag_last_index.json)")
    parser.add_argument("--verbose", action="store_true", help="Print detailed progress")
    args = parser.parse_args()

    if args.verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s  %(levelname)s  %(message)s")

    reindex(incremental=args.incremental)
