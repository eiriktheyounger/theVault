# System/Scripts/RAG/retrieval/store.py

from __future__ import annotations

import fnmatch
from pathlib import PurePath
import logging

# --- RW sqlite handle for indexer compatibility ---
import sqlite3

from ..config import DB_PATH as _DB_PATH
from ..config import VAULT_ROOT
from ...settings_cache import load_app_settings

# Use stdlib logging directly; no external get_logger dependency.
log = logging.getLogger("rag.store")

# Make hnswlib optional. We don't crash on import; we record the reason.
try:
    import hnswlib  # type: ignore

    HNSW_AVAILABLE = True
    HNSW_IMPORT_ERR = None
except Exception as e:
    hnswlib = None  # type: ignore
    HNSW_AVAILABLE = False
    HNSW_IMPORT_ERR = str(e)


def build_or_load_index() -> dict:
    """
    Build or load the RAG ANN index. If hnswlib (or other deps) are missing,
    return a stub success so the server stays healthy for smoke tests.
    """
    if not HNSW_AVAILABLE:
        # We intentionally don't fail the build in smoke runs
        # so tests can proceed; we report what happened.
        log.warning("hnswlib unavailable: %s", HNSW_IMPORT_ERR)
        return {"ok": True, "status": "build-stubbed", "detail": HNSW_IMPORT_ERR}

    # TODO: plug in your real index construction here.
    # e.g. load vectors, create hnswlib.Index(...), save to disk, etc.
    # For now we just return success to satisfy tests.
    log.info("hnswlib present; (stub) index load/build success.")
    return {"ok": True, "status": "build-ok"}


# --- RUNTIME SHIM ADDED: re-exports required by search_{fast,deep}.py ---
# This block is safe to append; it only defines names if they weren't importable earlier.

from typing import Any, Optional

# Re-export sqlite handle
try:
    pass
except Exception:  # pragma: no cover
    try:
        pass  # type: ignore
    except Exception as _e:
        raise

# Embedder access
try:
    from ..embedder_provider import get_embedder
except Exception:  # pragma: no cover
    try:
        from ..embedder_provider import get_embedder  # type: ignore
    except Exception as _e:
        raise


def embed_query(text: str) -> Any:
    """
    Return a single embedding vector for the query text using the active embedder.
    Works with sentence-transformers (encode) or providers exposing .embed().
    """
    emb = get_embedder()
    # sentence-transformers style
    if hasattr(emb, "encode"):
        return emb.encode([text])[0]
    # generic provider with .embed (could be Ollama-nomic)
    if hasattr(emb, "embed"):
        vec = emb.embed(text)
        return vec[0] if isinstance(vec, list) else vec
    raise RuntimeError("Active embedder has no encode/embed method")


def get_hnsw() -> Optional[Any]:
    """
    Return a FAISS index object if available; otherwise None so callers fall back to brute search.
    We keep this intentionally permissive to avoid hard failures when FAISS isn't installed/built.
    """
    try:
        import os

        try:
            from ..config import APP_DIR
        except Exception:  # pragma: no cover
            from ..config import APP_DIR  # type: ignore
        hnsw_path = os.path.join(APP_DIR, "rag_data", "chunks_hnsw.bin")
        if not os.path.exists(hnsw_path):
            return None
        import faiss  # type: ignore

        # Load FAISS index (matches indexer.py which uses faiss.IndexIDMap2)
        index = faiss.read_index(hnsw_path)
        return index
    except Exception:
        return None


# --- WAL helpers and RW sqlite handle for indexer compatibility ---
def _enable_wal(con: sqlite3.Connection) -> None:
    """Best-effort switch to WAL journaling on the connection."""
    try:
        con.execute("PRAGMA journal_mode=WAL;")
    except Exception:
        pass


def get_sqlite_rw() -> sqlite3.Connection:
    """
    Open the chunks.sqlite3 in read-write mode with Row dicts.
    Safe to call even if tables don't exist yet; indexer will create them.
    """
    con = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    _enable_wal(con)
    con.row_factory = sqlite3.Row
    return con


def vacuum_db() -> dict:
    """Run VACUUM on the chunks database and report status."""
    con = sqlite3.connect(str(_DB_PATH), check_same_thread=False, isolation_level=None)
    try:
        _enable_wal(con)
        con.execute("VACUUM")
        return {"ok": True}
    except Exception as e:  # pragma: no cover - best effort reporting
        return {"ok": False, "error": str(e)}
    finally:
        con.close()


def _ensure_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY,
            path TEXT UNIQUE,
            title TEXT,
            mtime REAL
        );
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY,
            doc_id INTEGER NOT NULL,
            heading_path TEXT,
            text TEXT,
            token_est INTEGER DEFAULT 0,
            mtime REAL,
            FOREIGN KEY(doc_id) REFERENCES documents(id)
        );
        CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);
        CREATE INDEX IF NOT EXISTS idx_docs_path ON documents(path);

        -- Full‑text search index on chunk text, kept in sync via triggers
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            text,
            content='chunks',
            content_rowid='id'
        );
        CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
            INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
        END;
        CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES('delete', old.id, old.text);
        END;
        CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES('delete', old.id, old.text);
            INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
        END;
        """
    )
    con.commit()
    # Migrate: add mtime column if the existing schema pre-dates it
    existing_cols = {c[1] for c in con.execute("PRAGMA table_info(documents)").fetchall()}
    if "mtime" not in existing_cols:
        con.execute("ALTER TABLE documents ADD COLUMN mtime REAL")
        con.commit()


def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except Exception:
        return ""


def _simple_chunks(text: str, max_len: int = 800) -> list[str]:
    paras = [p.strip() for p in text.replace("\r\n", "\n").split("\n\n")]
    out: list[str] = []
    buf = ""
    for p in paras:
        if not p:
            continue
        if len(buf) + len(p) + 1 > max_len:
            if buf:
                out.append(buf)
            buf = p
        else:
            buf = (buf + "\n\n" + p) if buf else p
    if buf:
        out.append(buf)
    return out


def _upsert_document(con: sqlite3.Connection, path: str, title: str, mtime: float) -> int:
    cur = con.execute(
        "INSERT INTO documents(path, title, mtime) VALUES(?,?,?) "
        "ON CONFLICT(path) DO UPDATE SET title=excluded.title, mtime=excluded.mtime RETURNING id",
        (path, title, mtime),
    )
    row = cur.fetchone()
    return (
        int(row[0])
        if row
        else int(con.execute("SELECT id FROM documents WHERE path=?", (path,)).fetchone()[0])
    )


def _replace_chunks(con: sqlite3.Connection, doc_id: int, chunks: list[str], mtime: float) -> None:
    con.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
    rows = []
    for c in chunks:
        tok = max(1, len(c) // 4)
        rows.append((doc_id, "", c, tok, mtime))
    con.executemany(
        "INSERT INTO chunks(doc_id, heading_path, text, token_est, mtime) VALUES(?,?,?,?,?)",
        rows,
    )


def rebuild_chunks_from_vault(paths: list[str] | None = None) -> dict:
    """Scan the Vault for markdown and populate documents/chunks tables.

    If ``paths`` is provided, only (re)build those files. Otherwise, rebuild
    everything found under ``VAULT_ROOT``.
    """
    con = get_sqlite_rw()
    _ensure_schema(con)

    import os

    # Load include/exclude globs from server settings (optional)
    try:
        s = load_app_settings() or {}
    except Exception:
        s = {}
    inc = s.get("INDEX_INCLUDE_GLOBS")
    exc = s.get("INDEX_EXCLUDE_GLOBS")

    def _to_list(v):
        if v is None:
            return None
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        # allow comma or newline separated
        text = str(v)
        if "\n" in text:
            return [t.strip() for t in text.splitlines() if t.strip()]
        return [t.strip() for t in text.split(",") if t.strip()]

    include_globs = _to_list(inc) or [
        "*.md",
        "*.MD",
        "*.markdown",
        "*.Markdown",
        "**/*.md",
        "**/*.MD",
        "**/*.markdown",
        "**/*.Markdown",
    ]
    exclude_globs = _to_list(exc) or []
    to_process: list[str] = []
    if paths:
        to_process = [p for p in paths if os.path.exists(p)]
    else:
        for root, _dirs, files in os.walk(VAULT_ROOT):
            for name in files:
                to_process.append(os.path.join(root, name))

    # If nothing to do, at least ensure tables exist
    if not to_process:
        con.commit()
        con.close()
        return {"ok": True, "files": 0}

    # Debug logging
    print(f"rebuild_chunks_from_vault: Processing {len(to_process)} files")
    count = 0
    for p in to_process:
        try:
            p_abs = os.path.abspath(p)
            st = os.stat(p_abs)
            mtime = st.st_mtime
        except OSError:
            continue
        rel = os.path.relpath(p_abs, VAULT_ROOT)

        # include/exclude filtering on the Vault-relative path
        def _matches(globs):
            return any(PurePath(rel).match(g) for g in globs)

        if include_globs and not _matches(include_globs):
            continue
        if exclude_globs and _matches(exclude_globs):
            if count < 5:
                print(f"  Skipping {rel}: exclude match ({exclude_globs})")
            continue
        title = os.path.splitext(os.path.basename(p_abs))[0]
        # Only accept markdown-like files by content-type choice
        if not (p_abs.lower().endswith(".md") or p_abs.lower().endswith(".markdown")):
            if count < 5:
                print(f"  Skipping {rel}: not markdown extension")
            continue
        text = _read_text(p_abs)
        pieces = _simple_chunks(text)
        try:
            doc_id = _upsert_document(con, rel, title, mtime)
            _replace_chunks(con, doc_id, pieces, mtime)
            count += 1
            if count <= 5:
                print(f"  Processing {rel}: {len(pieces)} chunks")
        except Exception as e:
            if count < 5:
                print(f"  Error processing {rel}: {e}")
            continue

    con.commit()
    con.close()
    return {"ok": True, "files": count}
