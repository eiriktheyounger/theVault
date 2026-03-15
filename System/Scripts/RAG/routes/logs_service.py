from __future__ import annotations

import os
import re
import time
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Response, WebSocket, WebSocketDisconnect

from ..logs import service as log_service

router = APIRouter(prefix="/logs", tags=["service-logs"])

_MIN_DATE_STR = os.getenv("LOG_MIN_DATE", "2025-09-09")
try:
    _Y, _M, _D = [int(x) for x in _MIN_DATE_STR.split("-")]
    _MIN_DATE = date(_Y, _M, _D)
except Exception:
    _MIN_DATE = date(1970, 1, 1)

_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def _include_line(line: str) -> bool:
    m = _DATE_RE.search(line)
    if not m:
        # If no date present, drop to trim older noise
        return False
    try:
        y, mth, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return date(y, mth, d) >= _MIN_DATE
    except Exception:
        return False


@router.get("/tail")
def tail(service: str, lines: int = Query(100, ge=1, le=1000)) -> Response:
    """Return the last ``lines`` from the service's log file as plain text.

    The UI expects a text/plain body with one entry per line.
    """

    try:
        content = [ln for ln in log_service.tail(service, lines) if _include_line(ln)]
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown service")
    body = "\n".join(content)
    return Response(body, media_type="text/plain")


@router.websocket("/stream")
async def stream(websocket: WebSocket, service: str) -> None:
    """Stream new log lines as they are written."""

    try:
        gen = log_service.follow(service)
    except KeyError:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    try:
        async for line in gen:
            if not _include_line(line):
                continue
            await websocket.send_json({"service": service, "ts": time.time(), "line": line})
    except WebSocketDisconnect:
        return
