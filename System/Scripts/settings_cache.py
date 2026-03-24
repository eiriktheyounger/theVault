"""Utilities for loading settings with an in-memory TTL cache."""

from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import os, yaml

DEFAULTS = {
    "LLM_URL": "http://127.0.0.1:5111/deep",
    "LLM_OFFLINE": False,
}

import json
import time
from pathlib import Path
from threading import Lock
from typing import Any, Dict

try:
    from .RAG.config import APP_DIR
except Exception:
    from .config import APP_DIR

_cache: dict[Path, tuple[Dict[str, Any], float]] = {}
_lock = Lock()


@lru_cache(maxsize=1)
def settings_cache() -> dict:
    cfg = dict(DEFAULTS)
    # Optional external settings
    settings_path = Path(os.getenv("NS_SETTINGS", "System/Config/settings.yaml"))
    if settings_path.exists():
        try:
            loaded = yaml.safe_load(settings_path.read_text()) or {}
            if isinstance(loaded, dict):
                cfg.update(loaded)
        except Exception:
            pass
    # Env overrides
    if "NS_LLM_URL" in os.environ:
        cfg["LLM_URL"] = os.getenv("NS_LLM_URL")
    if "NS_LLM_OFFLINE" in os.environ:
        cfg["LLM_OFFLINE"] = os.getenv("NS_LLM_OFFLINE") in ("1", "true", "True")
    return cfg


def load_settings(path: str | Path, *, ttl: float = 60) -> Dict[str, Any]:
    """Return settings from *path*, caching results for ``ttl`` seconds.

    The underlying file is only re-read when the cached value has expired,
    reducing disk I/O for frequently accessed configuration.
    """

    p = Path(path)
    now = time.monotonic()
    with _lock:
        entry = _cache.get(p)
        if entry:
            data, ts = entry
            if now - ts < ttl:
                return data
        data = json.loads(p.read_text())
        _cache[p] = (data, now)
        return data


def load_app_settings() -> Dict[str, Any]:
    """Return app settings from ``APP_DIR / 'settings.json'`` with a short TTL."""

    try:
        data = load_settings(APP_DIR / "settings.json", ttl=5)
    except Exception:
        return {}
    return data.get("settings", data)
