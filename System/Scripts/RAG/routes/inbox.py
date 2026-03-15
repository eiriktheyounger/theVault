# System/Scripts/RAG/routes/inbox.py
"""Inbox management API endpoints."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter

from .. import config

router = APIRouter(prefix="/inbox", tags=["inbox"])


@router.get("/info")
def get_inbox_info() -> Dict[str, Any]:
    """
    Return inbox directory paths and file counts.

    Expected by UI at: GET /inbox/info

    Returns:
        ok: bool - always True if endpoint reached
        paths: dict - mapping of inbox type to file path
        counts: dict - mapping of inbox type to file count
    """
    inbox_paths = {
        "audio": str(config.AUDIO_INBOX),
        "eml": str(config.EML_INBOX),
        "md_only": str(config.PLAUD_MD_ONLY_INBOX),
        "word": str(config.WORD_INBOX),
        "pdf": str(config.PDF_INBOX),
        "images": str(config.IMAGES_INBOX),
    }

    counts = {}
    total = 0

    for key, path_str in inbox_paths.items():
        path = Path(path_str)
        if not path.exists():
            counts[key] = 0
            continue

        # Count files (not directories or .DS_Store)
        file_count = sum(
            1 for item in path.rglob("*")
            if item.is_file() and item.name != ".DS_Store"
        )
        counts[key] = file_count
        total += file_count

    counts["total"] = total

    return {
        "ok": True,
        "paths": inbox_paths,
        "counts": counts,
    }
