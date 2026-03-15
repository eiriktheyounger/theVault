"""Service management API endpoints."""
from __future__ import annotations

import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/services", tags=["services"])


# ============================================================================
# Models
# ============================================================================

class ServiceStatus(BaseModel):
    """Status of a single service."""
    name: str
    running: bool
    pid: int | None = None
    details: str = ""


class ServicesStatusResponse(BaseModel):
    """Overall service status response."""
    services: List[ServiceStatus]
    all_running: bool
    all_stopped: bool


class ServiceActionResponse(BaseModel):
    """Response from service action."""
    success: bool
    message: str
    output: str
    services: List[ServiceStatus]


# ============================================================================
# Service Detection
# ============================================================================

def check_process_running(pattern: str) -> tuple[bool, int | None]:
    """Check if a process matching the pattern is running.

    Returns:
        Tuple of (is_running, pid)
    """
    try:
        result = subprocess.run(
            ['pgrep', '-f', pattern],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            return True, int(pids[0]) if pids else None
        return False, None
    except Exception as e:
        logger.error(f"Error checking process {pattern}: {e}")
        return False, None


def check_port_in_use(port: int) -> tuple[bool, int | None]:
    """Check if a specific port is in use and return the PID.

    Returns:
        Tuple of (is_running, pid)
    """
    try:
        result = subprocess.run(
            ['lsof', '-ti', f':{port}'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            return True, int(pids[0]) if pids else None
        return False, None
    except Exception as e:
        logger.error(f"Error checking port {port}: {e}")
        return False, None


def get_all_service_statuses() -> List[ServiceStatus]:
    """Get status of all NeroSpicy services."""
    # Define services with either pattern or port
    service_checks = [
        ("Ollama", "pattern", "ollama serve", None),
        ("LLM Server", "pattern", "uvicorn.*llm.server", None),
        ("RAG Server", "port", None, 5055),
        ("Stream Diagnostics API", "port", None, 8002),
        ("UI (Vite)", "port", None, 5173),
        ("Stream Diagnostics UI", "port", None, 5181),
        ("Vault Organizer UI", "port", None, 5175),
    ]

    statuses = []
    for name, check_type, pattern, port in service_checks:
        if check_type == "pattern":
            running, pid = check_process_running(pattern)
        else:  # port
            running, pid = check_port_in_use(port)

        status = ServiceStatus(
            name=name,
            running=running,
            pid=pid,
            details=f"PID {pid}" if pid else "Not running"
        )
        statuses.append(status)

    return statuses


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/status", response_model=ServicesStatusResponse)
async def get_services_status():
    """Get status of all NeroSpicy services."""
    try:
        statuses = get_all_service_statuses()
        all_running = all(s.running for s in statuses)
        all_stopped = all(not s.running for s in statuses)

        return ServicesStatusResponse(
            services=statuses,
            all_running=all_running,
            all_stopped=all_stopped
        )
    except Exception as e:
        logger.error(f"Error getting service status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start", response_model=ServiceActionResponse)
async def start_services():
    """Start all NeroSpicy services."""
    try:
        project_root = Path.home() / "theVault"
        venv_python = project_root / ".venv" / "bin" / "python"
        start_script = project_root / "System" / "Scripts" / "Services" / "start_all.py"

        if not start_script.exists():
            raise HTTPException(
                status_code=500,
                detail=f"Start script not found: {start_script}"
            )

        # Run the start script
        result = subprocess.run(
            [str(venv_python), str(start_script)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Get updated statuses
        statuses = get_all_service_statuses()
        all_running = all(s.running for s in statuses)

        return ServiceActionResponse(
            success=result.returncode == 0,
            message="All services started" if all_running else "Some services failed to start",
            output=result.stdout + result.stderr,
            services=statuses
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Service startup timed out")
    except Exception as e:
        logger.error(f"Error starting services: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop", response_model=ServiceActionResponse)
async def stop_services():
    """Gracefully stop all NeroSpicy services."""
    try:
        project_root = Path.home() / "theVault"
        venv_python = project_root / ".venv" / "bin" / "python"
        stop_script = project_root / "System" / "Scripts" / "Services" / "stop_all.py"

        if not stop_script.exists():
            raise HTTPException(
                status_code=500,
                detail=f"Stop script not found: {stop_script}"
            )

        # Run the stop script
        result = subprocess.run(
            [str(venv_python), str(stop_script)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Get updated statuses
        statuses = get_all_service_statuses()
        all_stopped = all(not s.running for s in statuses)

        return ServiceActionResponse(
            success=result.returncode == 0,
            message="All services stopped" if all_stopped else "Some services still running",
            output=result.stdout + result.stderr,
            services=statuses
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Service shutdown timed out")
    except Exception as e:
        logger.error(f"Error stopping services: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kill", response_model=ServiceActionResponse)
async def kill_services():
    """Force kill all NeroSpicy services."""
    try:
        project_root = Path.home() / "theVault"
        venv_python = project_root / ".venv" / "bin" / "python"
        kill_script = project_root / "System" / "Scripts" / "Services" / "emergency_kill.py"

        if not kill_script.exists():
            raise HTTPException(
                status_code=500,
                detail=f"Kill script not found: {kill_script}"
            )

        # Run the emergency kill script
        result = subprocess.run(
            [str(venv_python), str(kill_script)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Also kill Ollama app if it's running
        try:
            subprocess.run(['killall', 'Ollama'], capture_output=True, timeout=5)
        except:
            pass

        # Get updated statuses
        statuses = get_all_service_statuses()
        all_stopped = all(not s.running for s in statuses)

        return ServiceActionResponse(
            success=all_stopped,
            message="All services killed" if all_stopped else "Some services may still be running",
            output=result.stdout + result.stderr,
            services=statuses
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Emergency kill timed out")
    except Exception as e:
        logger.error(f"Error killing services: {e}")
        raise HTTPException(status_code=500, detail=str(e))
