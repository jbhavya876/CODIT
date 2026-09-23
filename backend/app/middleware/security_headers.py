"""
Security response headers middleware.

Injects standard defensive HTTP headers on every response:
  - X-Content-Type-Options       : prevents MIME-type sniffing
  - X-Frame-Options               : prevents clickjacking via iframes
  - X-XSS-Protection              : legacy XSS filter for older browsers
  - Referrer-Policy               : limits referrer leakage
  - Permissions-Policy            : disables unused browser features
  - Content-Security-Policy       : restricts resource loading origins
  - Strict-Transport-Security     : enforces HTTPS (header only; TLS is the
                                    reverse-proxy's job — included for when
                                    the server sits behind nginx/cloudflare)
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ---------------------------------------------------------------------------
# Header values
# ---------------------------------------------------------------------------

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=(), payment=()",
    # CSP: allow same-origin resources; inline scripts/styles needed for Vite
    # dev builds and Mermaid rendering. Tighten further once a nonce strategy
    # is in place.
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    ),
    # Only sent when the server is behind TLS termination
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Appends defensive security headers to every HTTP response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            # Don't overwrite if the route handler set its own value
            if header not in response.headers:
                response.headers[header] = value
        return response
