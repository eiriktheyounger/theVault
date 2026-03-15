from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from ..config import VAULT_DIR as VAULT_ROOT
from ..storage import chats as storage

router = APIRouter(prefix="/chats", tags=["chats"])


@router.get("/list")
def list_sessions(mode: str = "", limit: int = 15) -> List[Dict[str, Any]]:
    """Return recent chat sessions."""

    return storage.list_sessions(mode, limit)


@router.get("/session")
def get_session(cid: str) -> Dict[str, Any]:
    data = storage.read_session(cid)
    if not data["items"]:
        raise HTTPException(status_code=404, detail="session not found")
    return data


@router.post("/pin")
def pin_session(cid: str) -> Dict[str, bool]:
    data = storage.read_session(cid)
    if not data["items"]:
        raise HTTPException(status_code=404, detail="session not found")
    path = storage.get_pin(cid)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="session not found")
    rel = str(path.relative_to(VAULT_ROOT))
    pins = storage.get_pins()
    pins[cid] = rel
    storage.set_pins(pins)
    return {"ok": True}


@router.delete("/pin")
def unpin_session(cid: str) -> Dict[str, bool]:
    pins = storage.get_pins()
    if cid in pins:
        pins.pop(cid, None)
        storage.set_pins(pins)
    return {"ok": True}
