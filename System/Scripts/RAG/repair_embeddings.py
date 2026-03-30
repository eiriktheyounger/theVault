"""
repair_embeddings.py — Find and re-embed orphan chunks missing from FAISS.

Usage:
    cd ~/theVault
    python3 -m System.Scripts.RAG.repair_embeddings [--dry-run] [--batch-size 64]

Finds chunk IDs in SQLite that have no corresponding FAISS vector,
re-embeds them via Ollama, and adds them to the index. Safe to run
multiple times — only processes what's missing.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import faiss
import numpy as np

from .config import DB_PATH, HNSW_PATH, META_CSV_PATH
from .embedder_provider import get_embedder
from .retrieval.store import get_sqlite_rw


def _get_faiss_ids(index: faiss.Index) -> set[int]:
    """Extract all vector IDs currently in the FAISS index."""
    n = index.ntotal
    if n == 0:
        return set()
    # IDMap2 stores IDs in an int64 array accessible via id_map
    try:
        id_map = faiss.vector_to_array(index.id_map)
        return set(id_map.tolist())
    except Exception:
        # Fallback: reconstruct won't work for all index types,
        # but IDMap2 should always have id_map
        print("  [repair] WARNING: Could not read FAISS id_map, cannot determine orphans")
        sys.exit(1)


def find_orphans(con, faiss_ids: set[int]) -> list[dict]:
    """Find chunks in SQLite that have no FAISS vector."""
    rows = con.execute(
        "SELECT c.id AS chunk_rowid, d.path, d.title, "
        "c.heading_path AS heading, c.text, c.mtime "
        "FROM chunks c JOIN documents d ON d.id = c.doc_id "
        "ORDER BY c.id"
    ).fetchall()

    orphans = []
    for r in rows:
        if int(r["chunk_rowid"]) not in faiss_ids:
            orphans.append(dict(r))
    return orphans


def diagnose_orphans(orphans: list[dict]) -> dict:
    """Categorize why chunks might have failed embedding."""
    empty = [o for o in orphans if not (o["text"] or "").strip()]
    too_short = [o for o in orphans if 0 < len((o["text"] or "").strip()) < 5]
    normal = [o for o in orphans if len((o["text"] or "").strip()) >= 5]
    return {"empty": empty, "too_short": too_short, "normal": normal}


def repair(
    dry_run: bool = False,
    batch_size: int = 64,
    retry_empty: bool = False,
) -> dict:
    """Main repair function. Returns stats dict."""

    if not HNSW_PATH.exists():
        print("  [repair] ERROR: No FAISS index found at", HNSW_PATH)
        sys.exit(1)

    if not DB_PATH.exists():
        print("  [repair] ERROR: No SQLite DB found at", DB_PATH)
        sys.exit(1)

    print(f"  [repair] Loading FAISS index from {HNSW_PATH}")
    index = faiss.read_index(str(HNSW_PATH))
    faiss_ids = _get_faiss_ids(index)
    print(f"  [repair] FAISS has {len(faiss_ids)} vectors")

    con = get_sqlite_rw()
    total_chunks = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    print(f"  [repair] SQLite has {total_chunks} chunks")

    orphans = find_orphans(con, faiss_ids)
    print(f"  [repair] Found {len(orphans)} orphan chunks (in DB, not in FAISS)")

    if not orphans:
        print("  [repair] Nothing to repair!")
        return {"total_chunks": total_chunks, "faiss_before": len(faiss_ids),
                "orphans": 0, "embedded": 0, "failed": 0, "skipped": 0}

    diagnosis = diagnose_orphans(orphans)
    print(f"  [repair] Diagnosis: {len(diagnosis['empty'])} empty, "
          f"{len(diagnosis['too_short'])} too_short (<5 chars), "
          f"{len(diagnosis['normal'])} normal")

    if dry_run:
        print("\n  [repair] DRY RUN — no changes made. Sample orphans:")
        for o in orphans[:10]:
            text_preview = (o["text"] or "")[:80].replace("\n", " ")
            print(f"    ID {o['chunk_rowid']}: [{o['path']}] {text_preview}...")
        return {"total_chunks": total_chunks, "faiss_before": len(faiss_ids),
                "orphans": len(orphans), "embedded": 0, "failed": 0,
                "skipped": 0, "dry_run": True}

    # Filter: skip empty chunks unless --retry-empty
    to_embed = diagnosis["normal"] + diagnosis["too_short"]
    skipped = diagnosis["empty"]
    if retry_empty:
        to_embed = orphans
        skipped = []

    if not to_embed:
        print("  [repair] All orphans are empty-text chunks. Nothing to embed.")
        print(f"  [repair] Run with --retry-empty to attempt them, or delete them from SQLite.")
        return {"total_chunks": total_chunks, "faiss_before": len(faiss_ids),
                "orphans": len(orphans), "embedded": 0, "failed": 0,
                "skipped": len(skipped)}

    print(f"  [repair] Embedding {len(to_embed)} chunks, skipping {len(skipped)} empty...")

    provider = get_embedder()
    embedded = 0
    failed = 0
    failed_ids = []
    start = time.time()

    for i in range(0, len(to_embed), batch_size):
        batch = to_embed[i:i + batch_size]
        texts = [o["text"] or "" for o in batch]
        ids = [int(o["chunk_rowid"]) for o in batch]

        raw_vecs = provider.encode(texts)

        valid = [(v, sid) for v, sid in zip(raw_vecs, ids) if v and len(v) > 0]
        batch_failed = [(sid, t) for (v, sid), t in zip(zip(raw_vecs, ids), texts)
                        if not v or len(v) == 0]

        if valid:
            vecs_ok, ids_ok = zip(*valid)
            vecs = np.asarray(vecs_ok, dtype="float32")
            faiss.normalize_L2(vecs)
            id_batch = np.array(ids_ok, dtype="int64")
            index.add_with_ids(vecs, id_batch)
            embedded += len(valid)

        failed += len(batch_failed)
        failed_ids.extend([fid for fid, _ in batch_failed])

        batch_num = i // batch_size + 1
        total_batches = (len(to_embed) + batch_size - 1) // batch_size
        if batch_num % 10 == 0 or batch_num == total_batches:
            elapsed = time.time() - start
            print(f"  [repair] batch {batch_num}/{total_batches} | "
                  f"embedded={embedded} failed={failed} | {elapsed:.1f}s")

    # Save updated index
    print(f"  [repair] Writing updated FAISS index ({index.ntotal} vectors)...")
    faiss.write_index(index, str(HNSW_PATH))

    # Update meta.csv with newly embedded chunks
    if embedded > 0:
        try:
            import pandas as pd
            new_ids = set()
            for o in to_embed:
                if int(o["chunk_rowid"]) not in failed_ids:
                    new_ids.add(int(o["chunk_rowid"]))

            new_rows = []
            for o in to_embed:
                if int(o["chunk_rowid"]) in new_ids:
                    new_rows.append([
                        int(o["chunk_rowid"]),
                        o["path"],
                        o["title"],
                        o["heading"],
                        o["text"] or "",
                        o["mtime"],
                        max(1, len((o["text"] or "")) // 4),
                    ])

            if new_rows and META_CSV_PATH.exists():
                new_df = pd.DataFrame(
                    new_rows,
                    columns=["chunk_rowid", "path", "title", "heading",
                             "text", "mtime", "token_est"],
                )
                new_df.insert(0, "id", new_df["chunk_rowid"])
                old_df = pd.read_csv(META_CSV_PATH)
                # Don't duplicate rows
                old_df = old_df[~old_df["chunk_rowid"].isin(new_df["chunk_rowid"])]
                df = pd.concat([old_df, new_df], ignore_index=True)
                df.to_csv(META_CSV_PATH, index=False)
                print(f"  [repair] Updated meta.csv with {len(new_rows)} rows")
        except Exception as e:
            print(f"  [repair] WARNING: meta.csv update failed: {e}")

    # Report
    elapsed = time.time() - start
    final_total = index.ntotal
    coverage = (final_total / total_chunks * 100) if total_chunks > 0 else 0

    print(f"\n  [repair] === COMPLETE ===")
    print(f"  [repair] FAISS before: {len(faiss_ids)} vectors")
    print(f"  [repair] FAISS after:  {final_total} vectors")
    print(f"  [repair] Embedded:     {embedded}")
    print(f"  [repair] Failed:       {failed}")
    print(f"  [repair] Skipped:      {len(skipped)} (empty text)")
    print(f"  [repair] Coverage:     {coverage:.1f}% ({final_total}/{total_chunks})")
    print(f"  [repair] Time:         {elapsed:.1f}s")

    if failed_ids:
        log_path = Path("System/Scripts/RAG/rag_data/repair_failed_ids.txt")
        log_path.write_text("\n".join(str(fid) for fid in failed_ids) + "\n")
        print(f"  [repair] Failed IDs written to {log_path}")

    return {
        "total_chunks": total_chunks,
        "faiss_before": len(faiss_ids),
        "faiss_after": final_total,
        "orphans": len(orphans),
        "embedded": embedded,
        "failed": failed,
        "skipped": len(skipped),
        "coverage_pct": round(coverage, 1),
        "failed_ids": failed_ids,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Repair orphan FAISS embeddings")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show orphans without fixing them")
    parser.add_argument("--batch-size", type=int, default=64,
                        help="Embedding batch size (default: 64)")
    parser.add_argument("--retry-empty", action="store_true",
                        help="Also attempt to embed chunks with empty text")
    args = parser.parse_args()

    result = repair(
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        retry_empty=args.retry_empty,
    )

    if result.get("failed", 0) > 0:
        sys.exit(2)  # Signal partial failure
    sys.exit(0)
