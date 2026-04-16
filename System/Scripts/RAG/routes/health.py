from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Request

from ...build_info import BUILD_ID
from ..config import FAST_MODEL, DEEP_MODEL

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/about")
def about(request: Request) -> Dict[str, Any]:
    return {
        "name": "llm",
        "contract_version": "v2",
        "fast_lane": bool(getattr(request.app.state, "fast_model_ok", False)),
        "deep_lane": bool(getattr(request.app.state, "deep_model_ok", False)),
        "fast_model": FAST_MODEL,
        "deep_model": DEEP_MODEL,
    }


@router.get("/build")
def build() -> Dict[str, str]:
    """Return build metadata for the running service."""

    return {"build": BUILD_ID}
