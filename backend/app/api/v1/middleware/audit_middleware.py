"""Audit log middleware - records mutating requests."""
from __future__ import annotations

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

log = structlog.get_logger(__name__)

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: object) -> Response:
        response: Response = await call_next(request)  # type: ignore[operator]

        if request.method in _MUTATING_METHODS and response.status_code < 400:
            log.info(
                "audit_action",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                client_ip=request.client.host if request.client else "unknown",
            )

        return response
