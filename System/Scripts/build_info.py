"""Utility to expose build metadata loaded from build_info.yml."""

from __future__ import annotations

from pathlib import Path

import yaml


def _load_build_id() -> str:
    """Return the build_id from build_info.yml.

    If the file is missing or malformed, ``"unknown"`` is returned.
    """

    build_path = Path(__file__).resolve().parent / "build_info.yml"
    try:
        data = yaml.safe_load(build_path.read_text(encoding="utf-8")) or {}
        return str(data.get("build_id", "unknown"))
    except Exception:
        return "unknown"


BUILD_ID: str = _load_build_id()


__all__ = ["BUILD_ID"]
