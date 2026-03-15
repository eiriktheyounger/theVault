"""
rag_healthcheck.py — quick validations to catch drift early.

Run:
  python rag_healthcheck.py || true
"""

from __future__ import annotations

import json
import sqlite3
import sys

from sentence_transformers import SentenceTransformer

from .config import (
    APP_DIR,
    EMBED_DIM,
    HNSW_PATH,
    NS_EMBED_MODEL,
    RAG_DIR,
    SQLITE_PATH,
)

results = {"ok": True, "checks": []}


def add(name: str, ok: bool, info: dict) -> None:
    results["checks"].append({"name": name, "ok": ok, **info})
    results["ok"] = results["ok"] and ok


# Paths exist
add(
    "paths",
    APP_DIR.exists() and RAG_DIR.exists(),
    {
        "app_dir": str(APP_DIR),
        "rag_dir": str(RAG_DIR),
    },
)

# Embedding dim sanity
try:
    m = SentenceTransformer(NS_EMBED_MODEL)
    actual = int(m.get_sentence_embedding_dimension())
    add(
        "embed_dim",
        actual == EMBED_DIM,
        {
            "model": NS_EMBED_MODEL,
            "cfg_dim": EMBED_DIM,
            "actual_dim": actual,
        },
    )
except Exception as e:
    add("embed_dim", False, {"error": str(e), "model": NS_EMBED_MODEL})

# SQLite checks
if SQLITE_PATH.exists():
    try:
        con = sqlite3.connect(str(SQLITE_PATH))
        cur = con.cursor()
        docs = cur.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        chks = cur.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        add("sqlite_tables", True, {"documents": docs, "chunks": chks})
        con.close()
    except Exception as e:
        add("sqlite_tables", False, {"error": str(e)})
else:
    add("sqlite_tables", False, {"error": "missing_sqlite", "path": str(SQLITE_PATH)})

# HNSW presence
add("hnsw_exists", HNSW_PATH.exists(), {"path": str(HNSW_PATH)})

print(json.dumps(results, indent=2))
sys.exit(0 if results["ok"] else 1)
