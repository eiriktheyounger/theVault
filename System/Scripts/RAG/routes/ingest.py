# System/Scripts/RAG/routes/ingest.py
"""Ingest orchestration API endpoints."""
from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Query
from pydantic import BaseModel

from .. import config

router = APIRouter(prefix="/ingest", tags=["ingest"])


# ============================================================================
# Job State Management (In-Memory for MVP)
# ============================================================================

class IngestJob(BaseModel):
    """Represents an ingest job state."""
    job_id: str
    phase: str  # queued, running, finished, failed
    started_at: float
    finished_at: Optional[float] = None
    counts: Dict[str, int] = {}
    error: Optional[str] = None


# In-memory job storage (TODO: move to database for production)
_active_jobs: Dict[str, IngestJob] = {}


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/start")
async def start_ingest(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """
    Start an ingest job to process inbox files.

    Expected by UI at: POST /ingest/start

    Returns:
        ok: bool - True if job created
        job_id: str - unique job identifier
        error: optional error message
    """
    job_id = str(uuid.uuid4())

    # Create job in queued state
    job = IngestJob(
        job_id=job_id,
        phase="queued",
        started_at=time.time(),
        counts={
            "files_discovered": 0,
            "files_processed": 0,
            "files_succeeded": 0,
            "files_failed": 0,
        },
    )

    _active_jobs[job_id] = job

    # Start background processing
    background_tasks.add_task(_process_inbox_files_background, job_id)

    return {
        "ok": True,
        "job_id": job_id,
    }


@router.get("/status")
def get_ingest_status(
    id: str = Query(..., description="Job ID to check")
) -> Dict[str, Any]:
    """
    Get status of an ingest job.

    Expected by UI at: GET /ingest/status?id={job_id}

    Args:
        id: Job identifier from /ingest/start

    Returns:
        ok: bool - True if job found
        job_id: str - job identifier
        phase: str - current phase (queued, running, finished, failed)
        counts: dict - processing statistics
        started_at: float - unix timestamp
        finished_at: optional float - unix timestamp
        error: optional error message
    """
    job = _active_jobs.get(id)

    if not job:
        return {
            "ok": False,
            "job_id": id,
            "phase": "unknown",
            "error": f"Job {id} not found",
            "counts": {},
        }

    return {
        "ok": True,
        "job_id": job.job_id,
        "phase": job.phase,
        "counts": job.counts,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "error": job.error,
    }


# ============================================================================
# Helper Functions
# ============================================================================

def _process_inbox_files_background(job_id: str):
    """
    Background task to process inbox files.

    Calls the orchestration system to process all inbox files.
    """
    import logging

    logger = logging.getLogger(__name__)
    job = _active_jobs.get(job_id)

    if not job:
        logger.error(f"Job {job_id} not found in _process_inbox_files_background")
        return

    try:
        # Update job to running
        job.phase = "running"
        logger.info(f"Starting ingest job {job_id}")

        # Import and run the orchestration system
        from ...orchestration_system_start import run_orchestration

        # Run the orchestration (this processes all inboxes)
        run_orchestration()

        # Mark job as finished
        job.phase = "finished"
        job.finished_at = time.time()

        # Update counts based on logs (best effort)
        # The orchestration system logs events, but doesn't return counts
        # For now, just mark as complete
        job.counts["files_processed"] = 1  # Placeholder

        logger.info(f"Ingest job {job_id} completed successfully")

    except Exception as e:
        logger.error(f"Ingest job {job_id} failed: {e}", exc_info=True)
        job.phase = "failed"
        job.finished_at = time.time()
        job.error = str(e)
