"""Task Sync API endpoints for theVaultPilot sync system."""
from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/task-sync", tags=["task-sync"])

# Path to theVaultPilot sync script
SYNC_SCRIPT = Path.home() / "theVault" / "theVaultPilot" / "scripts" / "sync_now.py"
VAULT_PATH = Path.home() / "theVault" / "Vault"


# ============================================================================
# Request/Response Models
# ============================================================================

class SyncRequest(BaseModel):
    """Request to trigger task sync."""
    dry_run: bool = False


class SyncStatusRequest(BaseModel):
    """Request to get sync status."""
    vault_path: Optional[str] = None
    reminders_list: str = "Vault"


class SyncResponse(BaseModel):
    """Sync execution response."""
    success: bool
    reminders_created: int
    reminders_updated: int
    tasks_completed: int
    reminders_cleaned: int
    errors: list[str]
    duration_seconds: float
    stdout: str
    stderr: str


class SyncStatusResponse(BaseModel):
    """Sync status response."""
    success: bool
    total_tasks: int
    incomplete_tasks: int
    incomplete_reminders: int
    matched_pairs: int
    tasks_without_reminders: int
    reminders_without_tasks: int
    healthy: bool
    message: str


# ============================================================================
# Helper Functions
# ============================================================================

def _run_sync_command(args: list[str], timeout: int = 300) -> tuple[str, str, int]:
    """
    Run sync command and return (stdout, stderr, exit_code).

    Args:
        args: Command arguments (e.g., ["--dry-run"])
        timeout: Command timeout in seconds (default: 300 = 5 minutes)

    Returns:
        Tuple of (stdout, stderr, exit_code)
    """
    cmd = ["python3", str(SYNC_SCRIPT)] + args

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(SYNC_SCRIPT.parent.parent)
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", f"Sync command timed out after {timeout} seconds", 1
    except Exception as e:
        return "", f"Failed to run sync command: {e}", 1


def _parse_sync_output(stdout: str) -> Dict[str, int]:
    """
    Parse sync output to extract counts.

    Expected format in stdout:
        SYNC RESULTS
        ============================================================
        Reminders created:     17
        Reminders updated:      0
        Tasks completed:        3
        Reminders cleaned:      0

    Returns:
        Dict with counts or defaults if parsing fails
    """
    counts = {
        "reminders_created": 0,
        "reminders_updated": 0,
        "tasks_completed": 0,
        "reminders_cleaned": 0
    }

    try:
        for line in stdout.splitlines():
            line = line.strip()
            if "Reminders created:" in line:
                counts["reminders_created"] = int(line.split()[-1])
            elif "Reminders updated:" in line:
                counts["reminders_updated"] = int(line.split()[-1])
            elif "Tasks completed:" in line:
                counts["tasks_completed"] = int(line.split()[-1])
            elif "Reminders cleaned:" in line:
                counts["reminders_cleaned"] = int(line.split()[-1])
    except Exception as e:
        logger.warning(f"Failed to parse sync output: {e}")

    return counts


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/sync", response_model=SyncResponse)
async def trigger_sync(request: SyncRequest) -> SyncResponse:
    """
    Trigger Obsidian ↔ Apple Reminders sync.

    Runs the theVaultPilot sync script to synchronize tasks between
    Obsidian vault and Apple Reminders. Can be run in dry-run mode
    to preview changes without making them.

    Args:
        request: SyncRequest with dry_run flag

    Returns:
        SyncResponse with sync results and counts

    Raises:
        HTTPException: If sync script not found or fails
    """
    # Validate sync script exists
    if not SYNC_SCRIPT.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Sync script not found: {SYNC_SCRIPT}"
        )

    # Validate vault exists
    if not VAULT_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Vault path not found: {VAULT_PATH}. Check NAS mount if using symlink."
        )

    # Build command
    args = ["--verbose"]
    if request.dry_run:
        args.append("--dry-run")

    logger.info(f"Running task sync (dry_run={request.dry_run})...")

    # Run sync in background
    import time
    start_time = time.time()
    stdout, stderr, exit_code = await asyncio.to_thread(
        _run_sync_command,
        args,
        timeout=300  # 5 minutes
    )
    duration = time.time() - start_time

    # Parse results
    counts = _parse_sync_output(stdout)

    # Extract errors from stderr or stdout
    errors = []
    if stderr:
        errors.append(stderr)
    if "Error" in stdout or "WARNING" in stdout:
        for line in stdout.splitlines():
            if "Error" in line or "WARNING" in line:
                errors.append(line.strip())

    success = (exit_code == 0) and (not errors or request.dry_run)

    logger.info(f"Sync completed in {duration:.1f}s (exit_code={exit_code}, success={success})")

    return SyncResponse(
        success=success,
        reminders_created=counts["reminders_created"],
        reminders_updated=counts["reminders_updated"],
        tasks_completed=counts["tasks_completed"],
        reminders_cleaned=counts["reminders_cleaned"],
        errors=errors,
        duration_seconds=duration,
        stdout=stdout,
        stderr=stderr
    )


@router.post("/status", response_model=SyncStatusResponse)
async def get_sync_status(request: SyncStatusRequest) -> SyncStatusResponse:
    """
    Get current sync status without making changes.

    Checks the current state of tasks and reminders to report:
    - How many tasks/reminders exist
    - How many are matched vs unmatched
    - Whether sync is needed

    Args:
        request: SyncStatusRequest with optional vault_path and reminders_list

    Returns:
        SyncStatusResponse with current sync state

    Raises:
        HTTPException: If status check fails
    """
    # Validate sync script exists
    if not SYNC_SCRIPT.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Sync script not found: {SYNC_SCRIPT}"
        )

    # Run status command
    args = ["--status", "--reminders-list", request.reminders_list]
    if request.vault_path:
        args.extend(["--vault-path", request.vault_path])

    logger.info("Getting task sync status...")
    stdout, stderr, exit_code = await asyncio.to_thread(
        _run_sync_command,
        args,
        timeout=120  # 2 minutes
    )

    # Parse status output
    # Expected format:
    #   SYNC STATUS
    #   Total tasks in vault:       8824
    #   Incomplete tasks:           14
    #   Incomplete reminders:       14
    #   Matched pairs:              14
    #   Tasks without reminders:    0
    #   Reminders without tasks:    0
    #   ✅ All tasks and reminders are matched

    status = {
        "total_tasks": 0,
        "incomplete_tasks": 0,
        "incomplete_reminders": 0,
        "matched_pairs": 0,
        "tasks_without_reminders": 0,
        "reminders_without_tasks": 0,
        "healthy": False,
        "message": "Unknown status"
    }

    try:
        for line in stdout.splitlines():
            line = line.strip()
            if "Total tasks in vault:" in line:
                status["total_tasks"] = int(line.split()[-1])
            elif "Incomplete tasks:" in line:
                status["incomplete_tasks"] = int(line.split()[-1])
            elif "Incomplete reminders:" in line:
                status["incomplete_reminders"] = int(line.split()[-1])
            elif "Matched pairs:" in line:
                status["matched_pairs"] = int(line.split()[-1])
            elif "Tasks without reminders:" in line:
                status["tasks_without_reminders"] = int(line.split()[-1])
            elif "Reminders without tasks:" in line:
                status["reminders_without_tasks"] = int(line.split()[-1])
            elif "✅" in line:
                status["healthy"] = True
                status["message"] = line.replace("✅", "").strip()
            elif "⚠️" in line:
                status["healthy"] = False
                status["message"] = line.replace("⚠️", "").strip()
    except Exception as e:
        logger.error(f"Failed to parse status output: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse status output: {e}"
        )

    success = (exit_code == 0)

    return SyncStatusResponse(
        success=success,
        **status
    )
