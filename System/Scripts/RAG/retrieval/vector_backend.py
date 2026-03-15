from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List

import numpy as np

from ..config import MAX_CANDIDATES
from .db import DB_PATH, get_sqlite_ro

_M: np.ndarray | None = None
_IDS: List[int] | None = None

# Cache normalized matrix to disk to avoid repeated heavy loads
CACHE_PATH: Path = DB_PATH.with_name("chunks_norm.npz")


def _load_matrix(limit: int = MAX_CANDIDATES):
    """Load the normalized embedding matrix up to ``limit`` rows.

    The database is consulted first to ensure the total number of rows does
    not exceed ``limit``.  The normalized matrix and ids are cached to disk and
    only reloaded when the underlying database has been modified.
    """

    global _M, _IDS
    if _M is not None:
        return

    con: sqlite3.Connection = get_sqlite_ro()

    total = con.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL").fetchone()[0]
    if total > limit:
        raise RuntimeError(f"{total} embeddings exceed MAX_CANDIDATES={limit}")

    if CACHE_PATH.exists() and CACHE_PATH.stat().st_mtime >= DB_PATH.stat().st_mtime:
        data = np.load(CACHE_PATH)
        _M = data["M"]
        _IDS = data["ids"].astype(int).tolist()
        return

    cur = con.execute(
        "SELECT id, embedding FROM chunks WHERE embedding IS NOT NULL LIMIT ?",
        (limit,),
    )
    ids, rows = [], []
    for _id, blob in cur.fetchall():
        v = (
            np.frombuffer(blob, dtype=np.float32)
            if isinstance(blob, (bytes, bytearray))
            else np.array(blob, dtype=np.float32)
        )
        ids.append(int(_id))
        rows.append(v)
    if rows:
        M = np.vstack(rows).astype(np.float32)
        M /= np.linalg.norm(M, axis=1, keepdims=True) + 1e-9
    else:
        M = np.zeros((0, 384), dtype=np.float32)
    _M, _IDS = M, ids
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.savez(CACHE_PATH, M=M, ids=np.array(ids, dtype=np.int64))


def brute_neighbors(q_emb: np.ndarray, topk: int) -> List[int]:
    _load_matrix()
    if _M is None or _M.shape[0] == 0:
        return []
    q = q_emb.astype(np.float32)
    q /= np.linalg.norm(q) + 1e-9
    sims = _M @ q
    k = min(topk, sims.size)
    idx = np.argpartition(-sims, kth=k - 1)[:k]
    idx = idx[np.argsort(-sims[idx])]
    return [_IDS[i] for i in idx.tolist()]
