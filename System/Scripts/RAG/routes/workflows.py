"""Workflow orchestration API endpoints."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Set
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflows", tags=["workflows"])

# ============================================================================
# Job State Management (In-Memory)
# ============================================================================

class WorkflowJob(BaseModel):
    """Represents a workflow job state."""
    job_id: str
    workflow_type: str  # "morning" or "evening"
    status: str  # "queued", "running", "paused", "complete", "error"
    date: str  # YYYY-MM-DD
    started_at: float
    completed_at: Optional[float] = None
    overall_progress: int = 0
    current_step: int = 0
    total_steps: int = 0
    steps: list[Dict[str, Any]] = []
    error: Optional[str] = None


# In-memory job storage
_active_jobs: Dict[str, WorkflowJob] = {}
_active_workflows: Dict[str, Any] = {}  # workflow instances
_websocket_connections: Dict[str, Set[WebSocket]] = {}  # job_id -> set of websockets


# ============================================================================
# Request/Response Models
# ============================================================================

class WorkflowStartRequest(BaseModel):
    """Request to start a workflow."""
    workflow_type: str  # "morning" or "evening"
    date: Optional[str] = None  # YYYY-MM-DD, defaults to today
    options: Dict[str, Any] = {}


class WorkflowStatusResponse(BaseModel):
    """Workflow status response."""
    job_id: str
    workflow_type: str
    status: str
    date: str
    overall_progress: int
    current_step: int
    total_steps: int
    started_at: float
    completed_at: Optional[float] = None
    duration: Optional[float] = None
    steps: list[Dict[str, Any]]
    error: Optional[str] = None


class WorkflowControlRequest(BaseModel):
    """Request to control a workflow."""
    action: str  # "pause", "resume", "stop", "retry_step"
    step: Optional[int] = None  # for retry_step


# ============================================================================
# WebSocket Message Broadcasting
# ============================================================================

async def broadcast_to_job(job_id: str, message: Dict[str, Any]):
    """Broadcast message to all WebSocket connections for a job."""
    if job_id not in _websocket_connections:
        return

    dead_connections = set()

    for websocket in _websocket_connections[job_id]:
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send to websocket: {e}")
            dead_connections.add(websocket)

    # Remove dead connections
    for dead in dead_connections:
        _websocket_connections[job_id].discard(dead)


# ============================================================================
# Workflow Progress Callback
# ============================================================================

def create_progress_callback(job_id: str):
    """Create a progress callback for a workflow."""

    def callback(step):
        """Called when workflow step updates."""
        job = _active_jobs.get(job_id)
        if not job:
            return

        # Update job state
        job.current_step = step.step_num
        job.steps = [s.to_dict() for s in _active_workflows[job_id].steps]

        # Calculate overall progress
        completed_steps = sum(1 for s in job.steps if s["status"] == "complete")
        total_progress = sum(s["progress"] for s in job.steps)
        job.overall_progress = int(total_progress / job.total_steps)

        # Broadcast update via WebSocket (async)
        message = {
            "type": "step_progress",
            "job_id": job_id,
            "step": step.step_num,
            "progress": step.progress,
            "status": step.status,
            "summary_lines": step.summary_lines,
            "timestamp": time.time()
        }

        # Create task to broadcast (non-blocking)
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(broadcast_to_job(job_id, message))
        except RuntimeError:
            # No event loop in this thread - skip WebSocket update
            pass

    return callback


# ============================================================================
# Background Task Execution
# ============================================================================

async def _run_workflow_background(job_id: str, workflow_type: str, date: str):
    """Run workflow in background."""
    import sys
    from pathlib import Path

    # Add to path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    job = _active_jobs.get(job_id)
    if not job:
        logger.error(f"Job {job_id} not found")
        return

    try:
        # Update job status
        job.status = "running"
        logger.info(f"Starting {workflow_type} workflow {job_id}")

        # Broadcast start message
        await broadcast_to_job(job_id, {
            "type": "workflow_start",
            "job_id": job_id,
            "workflow_type": workflow_type,
            "timestamp": time.time()
        })

        # Import and create workflow
        if workflow_type == "morning":
            from Workflows import MorningWorkflow
            workflow = MorningWorkflow(date=date, callback=create_progress_callback(job_id))
        else:
            from Workflows import EveningWorkflow
            workflow = EveningWorkflow(date=date, callback=create_progress_callback(job_id))

        # Store workflow instance
        _active_workflows[job_id] = workflow

        # Set up job
        job.total_steps = len(workflow.steps)

        # Run workflow (synchronous)
        result = workflow.run()

        # Update job state
        job.status = "complete" if result["success"] else "error"
        job.completed_at = result["completed_at"]
        job.overall_progress = 100
        job.steps = result["steps"]

        if not result["success"] and result.get("total_errors", 0) > 0:
            job.error = f"{result['total_errors']} step(s) failed"

        logger.info(f"{workflow_type} workflow {job_id} completed")

        # Broadcast completion
        await broadcast_to_job(job_id, {
            "type": "workflow_complete",
            "job_id": job_id,
            "status": job.status,
            "duration": result["duration"],
            "timestamp": time.time()
        })

    except Exception as e:
        logger.error(f"{workflow_type} workflow {job_id} failed: {e}", exc_info=True)
        job.status = "error"
        job.completed_at = time.time()
        job.error = str(e)

        # Broadcast error
        await broadcast_to_job(job_id, {
            "type": "workflow_error",
            "job_id": job_id,
            "error": str(e),
            "timestamp": time.time()
        })

    finally:
        # Cleanup
        if job_id in _active_workflows:
            del _active_workflows[job_id]


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/start")
async def start_workflow(request: WorkflowStartRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """
    Start a workflow (morning or evening).

    Args:
        request: Workflow start request

    Returns:
        Job ID and status
    """
    # Validate workflow type
    if request.workflow_type not in ["morning", "evening"]:
        raise HTTPException(status_code=400, detail="Invalid workflow_type. Must be 'morning' or 'evening'")

    # Use provided date or default to today
    date = request.date or datetime.now().strftime("%Y-%m-%d")

    # Create job ID
    job_id = str(uuid.uuid4())

    # Determine total steps
    total_steps = 7 if request.workflow_type == "morning" else 3

    # Create job
    job = WorkflowJob(
        job_id=job_id,
        workflow_type=request.workflow_type,
        status="queued",
        date=date,
        started_at=time.time(),
        total_steps=total_steps,
        steps=[]
    )

    _active_jobs[job_id] = job
    _websocket_connections[job_id] = set()

    # Start background task
    background_tasks.add_task(_run_workflow_background, job_id, request.workflow_type, date)

    return {
        "ok": True,
        "job_id": job_id,
        "workflow_type": request.workflow_type,
        "date": date,
        "total_steps": total_steps
    }


@router.get("/status/{job_id}")
def get_workflow_status(job_id: str) -> WorkflowStatusResponse:
    """
    Get status of a workflow job.

    Args:
        job_id: Job identifier

    Returns:
        Workflow status
    """
    job = _active_jobs.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    duration = None
    if job.completed_at:
        duration = job.completed_at - job.started_at

    return WorkflowStatusResponse(
        job_id=job.job_id,
        workflow_type=job.workflow_type,
        status=job.status,
        date=job.date,
        overall_progress=job.overall_progress,
        current_step=job.current_step,
        total_steps=job.total_steps,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration=duration,
        steps=job.steps,
        error=job.error
    )


@router.get("/list")
def list_workflows() -> Dict[str, Any]:
    """
    List all workflow jobs (active and recent).

    Returns:
        List of jobs
    """
    jobs = []
    for job in _active_jobs.values():
        duration = None
        if job.completed_at:
            duration = job.completed_at - job.started_at

        jobs.append({
            "job_id": job.job_id,
            "workflow_type": job.workflow_type,
            "status": job.status,
            "date": job.date,
            "overall_progress": job.overall_progress,
            "started_at": job.started_at,
            "duration": duration
        })

    # Sort by started_at (most recent first)
    jobs.sort(key=lambda j: j["started_at"], reverse=True)

    return {
        "ok": True,
        "jobs": jobs,
        "count": len(jobs)
    }


@router.websocket("/stream/{job_id}")
async def workflow_stream(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time workflow updates.

    Args:
        websocket: WebSocket connection
        job_id: Job identifier
    """
    await websocket.accept()

    # Check if job exists
    job = _active_jobs.get(job_id)
    if not job:
        await websocket.send_json({
            "type": "error",
            "error": f"Job {job_id} not found"
        })
        await websocket.close()
        return

    # Add connection to job's connection set
    if job_id not in _websocket_connections:
        _websocket_connections[job_id] = set()

    _websocket_connections[job_id].add(websocket)

    logger.info(f"WebSocket connected for job {job_id}")

    try:
        # Send initial state
        await websocket.send_json({
            "type": "initial_state",
            "job_id": job_id,
            "workflow_type": job.workflow_type,
            "status": job.status,
            "date": job.date,
            "overall_progress": job.overall_progress,
            "current_step": job.current_step,
            "total_steps": job.total_steps,
            "steps": job.steps,
            "timestamp": time.time()
        })

        # Keep connection open and handle incoming messages
        while True:
            # Wait for messages (to detect disconnect)
            data = await websocket.receive_text()

            # Echo or handle commands if needed
            # For now, just keep alive

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}")
    finally:
        # Remove connection
        if job_id in _websocket_connections:
            _websocket_connections[job_id].discard(websocket)


@router.post("/control/{job_id}")
async def control_workflow(job_id: str, request: WorkflowControlRequest) -> Dict[str, Any]:
    """
    Control a running workflow (pause/resume/stop).

    Args:
        job_id: Job identifier
        request: Control request

    Returns:
        Control result
    """
    job = _active_jobs.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Validate action
    if request.action not in ["pause", "resume", "stop", "retry_step"]:
        raise HTTPException(status_code=400, detail="Invalid action")

    # For now, return not implemented (workflows run to completion)
    # TODO: Implement pause/resume/stop logic
    return {
        "ok": False,
        "error": "Control actions not yet implemented - workflows run to completion"
    }


@router.delete("/job/{job_id}")
def delete_job(job_id: str) -> Dict[str, Any]:
    """
    Delete a completed workflow job from memory.

    Args:
        job_id: Job identifier

    Returns:
        Deletion result
    """
    if job_id not in _active_jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    job = _active_jobs[job_id]

    # Only allow deletion of completed/error jobs
    if job.status in ["running", "queued"]:
        raise HTTPException(status_code=400, detail="Cannot delete running job")

    # Clean up
    del _active_jobs[job_id]

    if job_id in _websocket_connections:
        # Close all websockets
        for ws in _websocket_connections[job_id]:
            try:
                asyncio.create_task(ws.close())
            except:
                pass
        del _websocket_connections[job_id]

    if job_id in _active_workflows:
        del _active_workflows[job_id]

    return {
        "ok": True,
        "message": f"Job {job_id} deleted"
    }


# ============================================================================
# Reset Ingest Endpoint
# ============================================================================

class ResetRequest(BaseModel):
    """Request to reset ingest."""
    hours: float = 1.0  # Default 1 hour
    dry_run: bool = False


@router.post("/reset")
async def reset_ingest(request: ResetRequest) -> Dict[str, Any]:
    """
    Reset ingest - move processed files back to inbox, delete outputs.

    Args:
        request: Reset parameters (hours, dry_run)

    Returns:
        Result with counts and log output
    """
    import subprocess
    import sys
    from pathlib import Path

    # Validate hours
    if request.hours <= 0 or request.hours > 336:
        raise HTTPException(status_code=400, detail="Hours must be between 0 and 336 (14 days)")

    # Run the reset script
    script_path = Path(__file__).parent.parent.parent / "Workflows" / "reset_ingest.py"

    cmd = [sys.executable, str(script_path), "--hours", str(request.hours)]
    if request.dry_run:
        cmd.append("--dry-run")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(Path.home() / "theVault")
        )

        return {
            "ok": result.returncode == 0,
            "log": result.stdout,
            "errors": result.stderr if result.stderr else None
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Reset timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
