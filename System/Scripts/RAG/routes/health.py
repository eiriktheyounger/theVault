from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import APIRouter, Request

from ...build_info import BUILD_ID

FAST_MODEL_DEFAULT = "phi3:latest"
DEEP_MODEL_DEFAULT = "llama3.1:8b"
FAST_MODEL = os.getenv("FAST_MODEL", FAST_MODEL_DEFAULT)
DEEP_MODEL = os.getenv("DEEP_MODEL", DEEP_MODEL_DEFAULT)

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
