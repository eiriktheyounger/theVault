# routes/index.py — index management endpoints

from __future__ import annotations

import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter

from ..config import DB_PATH, HNSW_PATH, META_CSV_PATH
from ..retrieval import indexer

router = APIRouter()


# In-memory status shared across requests
STATUS: Dict[str, Any] = {
    "ok": True,
    "job_id": "",
    "phase": "idle",
    "processed": 0,
    "succeeded": 0,
    "failed": 0,
    "skipped": 0,
    "vectors_total": 0,
    "docs_total": 0,
    "last_writes": [],
    "eta": None,
    "started_at": None,
    "finished_at": None,
    "progress": 0,
    "error": None,
}

_lock = threading.Lock()


def _progress_cb(phase: str, **metrics: Any) -> None:
    """Update STATUS with progress metrics from the indexer."""
    with _lock:
        STATUS["phase"] = phase
        # Lightweight progress heuristic by phase
        prog_map = {
            "start": 0.05,
            "discover": 0.1,
            "chunk": 0.3,
            "embed": 0.6,
            "upsert": 0.85,
            "verify": 0.95,
            "final": 1.0,
        }
        STATUS["progress"] = prog_map.get(phase, STATUS.get("progress", 0))
        for key in (
            "processed",
            "succeeded",
            "failed",
            "skipped",
            "vectors_total",
            "docs_total",
            "eta",
        ):
            if key in metrics:
                STATUS[key] = metrics[key]
        if "last_writes" in metrics:
            lw = metrics["last_writes"]
            STATUS["last_writes"] = list(lw) if isinstance(lw, list) else [lw]
        if "expected" in metrics:
            STATUS["docs_total"] = metrics["expected"]
        if "written" in metrics:
            STATUS["vectors_total"] = metrics["written"]
        if "ok" in metrics or "status" in metrics:
            # Final verification step may report ok/status
            if metrics.get("ok") is False or metrics.get("status") == "error":
                STATUS["ok"] = False


def _run_index(incremental: bool) -> None:
    try:
        indexer.reindex(progress_cb=_progress_cb, incremental=incremental)
        with _lock:
            STATUS["phase"] = "finished"
            STATUS["progress"] = 1.0
            STATUS["finished_at"] = int(time.time() * 1000)
    except Exception:
        with _lock:
            STATUS["phase"] = "failed"
            STATUS["ok"] = False
            STATUS["finished_at"] = int(time.time() * 1000)
            import traceback as _tb

            STATUS["error"] = _tb.format_exc(limit=1)


def _launch(incremental: bool) -> None:
    def task() -> None:
        with _lock:
            STATUS.update(
                phase="discover",
                processed=0,
                succeeded=0,
                failed=0,
                skipped=0,
                vectors_total=0,
                docs_total=0,
                last_writes=[],
                eta=None,
                started_at=int(time.time() * 1000),
                finished_at=None,
                progress=0.0,
                error=None,
            )
        _run_index(incremental)

    threading.Thread(target=task, daemon=True).start()


@router.post("/index/rebuild")
def rebuild() -> Dict[str, Any]:
    """Launch a background rebuild of the vector index."""
    job_id = str(int(time.time()))  # simple monotonic id for UI
    with _lock:
        STATUS["job_id"] = job_id
        STATUS["ok"] = True
        STATUS["mode"] = "build"
    _launch(False)
    return {"ok": True, "job_id": job_id}


@router.post("/index/update")
def update() -> Dict[str, Any]:
    """Launch an incremental update of the vector index."""
    job_id = str(int(time.time()))
    with _lock:
        STATUS["job_id"] = job_id
        STATUS["ok"] = True
        STATUS["mode"] = "update"
    _launch(True)
    return {"ok": True, "job_id": job_id}


@router.get("/index/status")
def status(job_id: str | None = None) -> Dict[str, Any]:
    """Return the current indexing status.

    The UI may call without a job_id; return the last known state.
    """
    with _lock:
        resp = STATUS.copy()
    # Ensure contract fields present
    resp.setdefault("ok", True)
    resp.setdefault("job_id", job_id or resp.get("job_id", ""))
    resp.setdefault("phase", "unknown")
    resp.setdefault("progress", 0)
    # Attach counts and lastUpdated snapshot for dashboard
    counts: Dict[str, int] = {}
    try:
        if Path(DB_PATH).exists():
            con = sqlite3.connect(str(DB_PATH))
            try:
                counts["docs"] = int(con.execute("select count(*) from documents").fetchone()[0])
            except Exception:
                counts.setdefault("docs", 0)
            try:
                counts["chunks"] = int(con.execute("select count(*) from chunks").fetchone()[0])
            except Exception:
                counts.setdefault("chunks", 0)
            con.close()
        counts["bytes_db"] = int(Path(DB_PATH).stat().st_size) if Path(DB_PATH).exists() else 0
        counts["bytes_index"] = (
            int(Path(HNSW_PATH).stat().st_size) if Path(HNSW_PATH).exists() else 0
        )
        counts["bytes_meta"] = (
            int(Path(META_CSV_PATH).stat().st_size) if Path(META_CSV_PATH).exists() else 0
        )
        resp["counts"] = counts
        # Last updated = newer of DB or index file mtime
        mtimes = [
            Path(DB_PATH).stat().st_mtime if Path(DB_PATH).exists() else 0,
            Path(HNSW_PATH).stat().st_mtime if Path(HNSW_PATH).exists() else 0,
            Path(META_CSV_PATH).stat().st_mtime if Path(META_CSV_PATH).exists() else 0,
        ]
        latest = max(mtimes) if mtimes else 0
        if latest:
            resp["lastUpdated"] = int(latest * 1000)
        # Simple state label
        if resp.get("phase") in ("finished",) and (counts.get("chunks", 0) > 0):
            resp["state"] = "ready"
        elif resp.get("phase") in ("failed",):
            resp["state"] = "failed"
        else:
            resp.setdefault("state", "idle")
    except Exception:
        # best-effort; leave counts/state absent on error
        pass
    return resp


@router.post("/index/clear")
def clear_index() -> Dict[str, Any]:
    """Remove index artifacts (DB, vector index, meta) and reset status.

    Next rebuild will recreate schema and artifacts. Safe to call while idle.
    """
    try:
        for p in (DB_PATH, HNSW_PATH, META_CSV_PATH, Path(".rag_last_index.json")):
            try:
                if Path(p).exists():
                    os.remove(p)
            except Exception:
                pass
        with _lock:
            STATUS.update(
                ok=True,
                job_id="",
                phase="idle",
                processed=0,
                succeeded=0,
                failed=0,
                skipped=0,
                vectors_total=0,
                docs_total=0,
                last_writes=[],
                eta=None,
                started_at=None,
                finished_at=None,
                progress=0,
                error=None,
            )
        return {"ok": True}
    except Exception as e:  # pragma: no cover - defensive
        return {"ok": False, "error": str(e)}
