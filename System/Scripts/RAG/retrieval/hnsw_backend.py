"""
retrieval/hnsw_backend.py — optional HNSW vector neighbor lookup.

Provides :func:`hnsw_neighbors` which queries the cached HNSW index.
The function requires the ``hnswlib`` package. If it is not installed,
a clear :class:`ImportError` is raised.
"""

from __future__ import annotations

from typing import List

import numpy as np


def hnsw_neighbors(q_emb: np.ndarray, topk: int) -> List[int]:
    """Return IDs of the ``topk`` nearest neighbors for ``q_emb``.

    Parameters
    ----------
    q_emb : np.ndarray
        Normalized query embedding.
    topk : int
        Number of nearest neighbors to return.

    Returns
    -------
    List[int]
        Ordered list of chunk IDs, or an empty list if the index is missing.
    """
    try:
        import hnswlib  # noqa: F401
    except ImportError as e:  # pragma: no cover - direct feedback is clearer
        raise ImportError(
            "hnsw_neighbors requires `hnswlib`. Install the package to use the HNSW backend."
        ) from e

    from .store import get_hnsw

    index = get_hnsw()
    if index is None:
        return []
    ids, _ = index.knn_query(q_emb, k=topk)
    return [int(x) for x in ids[0].tolist()]
