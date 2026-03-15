"""
logutil.py — tiny JSONL logger + timing helper

Why: predictable, greppable logs. Every major op writes one JSON line.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Optional

from .config import LOG_PATH, STRUCTLOG_ENABLED


class Timer:
    """Context manager measuring wall time in milliseconds."""

    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.elapsed = round((time.perf_counter() - self.t0) * 1000, 3)


def _emit(obj: dict):
    s = json.dumps(obj, ensure_ascii=False)
    sys.stdout.write(s + "\n")
    sys.stdout.flush()
    if STRUCTLOG_ENABLED:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(s + "\n")


def get_logger(name: Optional[str] = "rag"):
    class L:
        def info(self, event, **kw):
            _emit({"event": event, "level": "info", "logger": name, **kw})

        def warn(self, event, **kw):
            _emit({"event": event, "level": "warn", "logger": name, **kw})

        def error(self, event, **kw):
            _emit({"event": event, "level": "error", "logger": name, **kw})

    return L()


# --- compat: ensure get_logger() returns an object with .warning ------------
try:
    _probe = get_logger(__name__)  # type: ignore[name-defined]
except Exception:
    # If get_logger doesn't exist or fails, provide a no-op logger.
    class _NoopLogger:
        def info(self, *a, **k):
            return None

        def debug(self, *a, **k):
            return None

        def warning(self, *a, **k):
            return None

    def get_logger(name: str = __name__):  # type: ignore[no-redef]
        return _NoopLogger()
else:
    if not hasattr(_probe, "warning"):
        _orig_get_logger = get_logger  # type: ignore[name-defined]

        def get_logger(name: str = __name__):  # type: ignore[no-redef]
            base = _orig_get_logger(name)

            class _CompatLogger:
                def __init__(self, b):
                    self._b = b

                def info(self, *a, **k):
                    return getattr(self._b, "info", lambda *a, **k: None)(*a, **k)

                def debug(self, *a, **k):
                    return getattr(self._b, "debug", lambda *a, **k: None)(*a, **k)

                def warning(self, *a, **k):
                    # provide a harmless warning method
                    try:
                        w = getattr(self._b, "warning", None)
                        if callable(w):
                            return w(*a, **k)
                    except Exception:
                        pass
                    return None

            return _CompatLogger(base)
