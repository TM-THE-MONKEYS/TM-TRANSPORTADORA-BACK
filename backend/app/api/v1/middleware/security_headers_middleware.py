"""Middleware that injects recommended security response headers."""
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "0",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": (
        "camera=(), microphone=(), geolocation=()"
    ),
    "Cache-Control": "no-store",
    "Strict-Transport-Security": (
        "max-age=31536000; includeSubDomains"
    ),
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(  # type: ignore[override]
        self, request: Request, call_next: object
    ) -> Response:
        response: Response = await call_next(request)  # type: ignore[operator]
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response
