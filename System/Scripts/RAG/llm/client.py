"""Minimal client for deep LLM calls."""

from __future__ import annotations

from typing import Any

import requests

try:
    from ... import settings_cache  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - fallback for flattened imports
    import settings_cache  # type: ignore[no-redef, attr-defined]


def _resolve_url() -> str:
    cfg = settings_cache.settings_cache()
    url = cfg.get("LLM_URL") if isinstance(cfg, dict) else None
    if not isinstance(url, str) or not url:
        raise RuntimeError("LLM_URL is not configured in settings cache")
    return url


def call_deep(payload: dict[str, Any], timeout: float = 5.0) -> dict[str, Any]:
    """Send *payload* to the deep LLM endpoint and return the JSON response."""

    url = _resolve_url()
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:  # pragma: no cover
        raise RuntimeError(f"Failed to contact deep LLM at {url}: {exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:  # pragma: no cover
        raise RuntimeError("Deep LLM returned invalid JSON") from exc

    if not isinstance(data, dict):
        raise RuntimeError("Deep LLM returned unexpected payload type")
    return data
