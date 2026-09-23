"""
Request guard middleware.

Provides three complementary protections:

1. **Max body size** (default 50 MB)
   Reads the Content-Length header and rejects oversized requests before any
   route handler is called.  Streaming uploads that omit Content-Length are
   allowed through (the ZIP route validates its own buffer after reading).

2. **Request timeout** (default 300 s)
   Wraps the downstream call in asyncio.wait_for so long-running requests
   (e.g. a slow loris attack sending data 1 byte/s) are forcibly cancelled.

3. **Allowed hosts** (default "*" = disabled)
   When ALLOWED_HOSTS is set to a comma-separated list of hostnames, rejects
   requests whose Host header does not match.  Prevents host header injection
   attacks when the server is publicly exposed.
"""

from __future__ import annotations

import asyncio
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.app.config import Config

log = logging.getLogger(__name__)

# Pre-parse allowed hosts once at import time
_ALLOWED_HOSTS: list[str] | None = None

def _get_allowed_hosts() -> list[str] | None:
    global _ALLOWED_HOSTS
    if _ALLOWED_HOSTS is None:
        raw = Config.ALLOWED_HOSTS.strip()
        if not raw or raw == "*":
            _ALLOWED_HOSTS = []  # empty list = allow all
        else:
            _ALLOWED_HOSTS = [h.strip().lower() for h in raw.split(",") if h.strip()]
    return _ALLOWED_HOSTS


class RequestGuardMiddleware(BaseHTTPMiddleware):
    """Enforces body size limits, request timeouts, and host header validation."""

    def __init__(self, app, **kwargs):
        super().__init__(app, **kwargs)
        self._max_body_bytes = Config.MAX_REQUEST_BODY_MB * 1024 * 1024
        self._timeout = Config.REQUEST_TIMEOUT_SECONDS

    async def dispatch(self, request: Request, call_next) -> Response:
        # ------------------------------------------------------------------
        # 1. Host header validation
        # ------------------------------------------------------------------
        allowed = _get_allowed_hosts()
        if allowed:
            host = request.headers.get("host", "").split(":")[0].lower()
            if host not in allowed:
                log.warning("Rejected request: disallowed host '%s'", host)
                return JSONResponse(
                    status_code=400,
                    content={"error": {"code": "bad_host", "message": "Invalid Host header."}},
                )

        # ------------------------------------------------------------------
        # 2. Body size guard (Content-Length header check — fast path)
        # ------------------------------------------------------------------
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                cl = int(content_length)
                if cl > self._max_body_bytes:
                    log.warning(
                        "Rejected oversized request: %d bytes > %d byte limit (path=%s)",
                        cl, self._max_body_bytes, request.url.path,
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": {
                                "code": "request_too_large",
                                "message": (
                                    f"Request body too large. "
                                    f"Maximum allowed size is {Config.MAX_REQUEST_BODY_MB} MB."
                                ),
                            }
                        },
                    )
            except ValueError:
                pass  # malformed header — let the route handle it

        # ------------------------------------------------------------------
        # 3. Request timeout
        # ------------------------------------------------------------------
        try:
            response: Response = await asyncio.wait_for(
                call_next(request),
                timeout=self._timeout,
            )
            return response
        except asyncio.TimeoutError:
            log.warning(
                "Request timeout after %ds: %s %s",
                self._timeout, request.method, request.url.path,
            )
            return JSONResponse(
                status_code=504,
                content={
                    "error": {
                        "code": "request_timeout",
                        "message": (
                            f"Request exceeded the maximum processing time "
                            f"of {self._timeout}s and was cancelled."
                        ),
                    }
                },
            )
