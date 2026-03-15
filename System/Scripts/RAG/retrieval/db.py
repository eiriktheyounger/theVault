from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Union

from ..config import DB_PATH


def get_sqlite_ro(path: Union[str, Path] = DB_PATH) -> sqlite3.Connection:
    """
    Open chunks DB read-only with Row mapping.
    Works even if URI RO is blocked, by falling back to plain path.
    """
    p = str(path)
    try:
        con = sqlite3.connect(f"file:{p}?mode=ro", uri=True, check_same_thread=False)
        con.row_factory = sqlite3.Row
        return con
    except Exception:
        con = sqlite3.connect(p, check_same_thread=False)
        con.row_factory = sqlite3.Row
        return con
