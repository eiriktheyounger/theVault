#!/usr/bin/env python
import os
import sys

from .adapters.io_boundary import rag_search
from .adapters.schemas import RagResp

ENV_MODE = os.getenv("LLM_MODE", "live")


def search(q: str, k: int = 5) -> dict:
    """Return raw search results for ``q`` limited to ``k`` items."""
    data = rag_search(q, k)
    return RagResp.model_validate(data).model_dump()


def main(q: str, k: int = 10):
    data = search(q, k)
    results = data.get("results", [])
    for r in results:
        if isinstance(r, dict):
            score = r.get("score", 0.0)
            path = r.get("path", "")
            print(f"{score:.4f}  {path}")
        else:
            print(str(r))
    print(f"[INFO] results={len(results)} (ENV LLM_MODE={ENV_MODE})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python ~/theVault/System/Scripts/RAG/rag_query.py "your question" [k]')
        sys.exit(1)
    query = sys.argv[1]
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    main(query, k)
