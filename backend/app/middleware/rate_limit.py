"""
Per-IP sliding-window rate limiter middleware.

Route groups and their default limits (all configurable via environment):
  - analyze   : /api/analyze/run          →  RATE_LIMIT_ANALYZE_RPM  (default  4 / 60s)
  - ingest    : /api/ingest/*             →  RATE_LIMIT_INGEST_RPM   (default 10 / 60s)
  - report    : /api/report/markdown,
                /api/report/html          →  RATE_LIMIT_REPORT_RPM   (default 20 / 60s)
  - general   : everything else           →  RATE_LIMIT_GENERAL_RPM  (default 120 / 60s)

Implementation: zero extra dependencies — uses only stdlib collections.deque.
Each (IP, group) pair keeps a deque of request timestamps (epoch floats).
On each request the deque is trimmed to the window and the length checked.
A background daemon thread prunes idle keys every 60 seconds.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response




# ---------------------------------------------------------------------------
# Route → group mapping
# ---------------------------------------------------------------------------
_PREFIX_TO_GROUP: list[tuple[str, str]] = [
    ("/api/analyze/run", "analyze"),
    ("/api/ingest/",     "ingest"),
    ("/api/report/markdown", "report"),
    ("/api/report/html",     "report"),
]


def _route_group(path: str) -> str:
    for prefix, group in _PREFIX_TO_GROUP:
        if path.startswith(prefix):
            return group
    return "general"


# ---------------------------------------------------------------------------
# Limit registry — read dynamically from Config so env-var overrides in tests
# (e.g. os.environ["RATE_LIMIT_ENABLED"] = "false") take effect at runtime.
# ---------------------------------------------------------------------------
_WINDOW_SECONDS = 60


def _get_limit(group: str) -> int:
    """Return the per-minute request limit for a route group.

    Reads directly from os.environ so that test env-var overrides
    (set before app creation) are honoured even if Config class
    attributes were already evaluated at import time.
    """
    import os as _os
    defaults = {
        "analyze": "4",
        "ingest":  "10",
        "report":  "20",
        "general": "120",
    }
    env_keys = {
        "analyze": "RATE_LIMIT_ANALYZE_RPM",
        "ingest":  "RATE_LIMIT_INGEST_RPM",
        "report":  "RATE_LIMIT_REPORT_RPM",
        "general": "RATE_LIMIT_GENERAL_RPM",
    }
    return int(_os.environ.get(env_keys[group], defaults[group]))

# ---------------------------------------------------------------------------
# State — shared across all requests
# ---------------------------------------------------------------------------
# key: (ip, group)  →  deque of request timestamps
_buckets: Dict[Tuple[str, str], Deque[float]] = {}
_lock = threading.Lock()


def _prune_stale_buckets() -> None:
    """Remove bucket entries that have been idle for more than one window."""
    cutoff = time.monotonic() - _WINDOW_SECONDS
    with _lock:
        stale = [k for k, dq in _buckets.items() if not dq or dq[-1] < cutoff]
        for k in stale:
            del _buckets[k]


def _start_pruner() -> None:
    """Daemon thread that prunes stale buckets every 60 seconds."""
    def _loop():
        while True:
            time.sleep(_WINDOW_SECONDS)
            _prune_stale_buckets()

    t = threading.Thread(target=_loop, daemon=True, name="rate-limit-pruner")
    t.start()


_start_pruner()


# ---------------------------------------------------------------------------
# IP extraction helper
# ---------------------------------------------------------------------------

def _client_ip(request: Request) -> str:
    """
    Extract the real client IP.
    Respects X-Forwarded-For (first hop only) when present, falls back to
    the direct connection address.
    """
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window per-IP rate limiter."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Read enabled flag fresh each call so os.environ overrides in tests work
        import os as _os
        enabled = _os.environ.get("RATE_LIMIT_ENABLED", "true").lower() != "false"
        if not enabled:
            return await call_next(request)

        ip = _client_ip(request)
        group = _route_group(request.url.path)
        limit = _get_limit(group)
        now = time.monotonic()
        window_start = now - _WINDOW_SECONDS

        key = (ip, group)
        with _lock:
            if key not in _buckets:
                _buckets[key] = deque()
            dq = _buckets[key]

            # Drop timestamps outside the current window
            while dq and dq[0] < window_start:
                dq.popleft()

            count = len(dq)
            if count >= limit:
                # Oldest timestamp tells us when the window next resets
                retry_after = int(_WINDOW_SECONDS - (now - dq[0])) + 1
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "rate_limited",
                            "message": (
                                f"Too many requests. You have exceeded the "
                                f"{limit} requests / {_WINDOW_SECONDS}s limit "
                                f"for this endpoint group. "
                                f"Retry after {retry_after}s."
                            ),
                        }
                    },
                    headers={"Retry-After": str(retry_after)},
                )

            dq.append(now)

        return await call_next(request)
