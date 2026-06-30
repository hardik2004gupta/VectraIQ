"""
Security headers middleware.

Adds OWASP-recommended HTTP security headers to every response.
Does not modify existing headers set by route handlers.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security-related response headers to every outgoing response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # Prevent browsers from MIME-sniffing the content type
        response.headers.setdefault("X-Content-Type-Options", "nosniff")

        # Block clickjacking (deny iframe embedding)
        response.headers.setdefault("X-Frame-Options", "DENY")

        # Control referrer information sent to third parties
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")

        # Restrict browser features (camera, mic, etc.)
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )

        # CSP: API-only service — no need to load scripts, images, etc.
        # Allow SSE connections from same origin for streaming endpoint.
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; connect-src 'self'; frame-ancestors 'none'",
        )

        # Remove server identification header (added by uvicorn)
        response.headers.pop("Server", None)

        return response
