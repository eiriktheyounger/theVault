#!/usr/bin/env python3
"""CLI utility to VACUUM the RAG chunks SQLite database."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure repository root on sys.path for absolute imports
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from .retrieval.store import vacuum_db


def main() -> None:
    res = vacuum_db()
    print(json.dumps(res))


if __name__ == "__main__":
    main()
