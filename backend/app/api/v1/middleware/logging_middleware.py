"""Request logging middleware with request ID injection."""
from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging.structlog_config import set_request_id

log = structlog.get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: object) -> Response:
        request_id = str(uuid.uuid4())
        set_request_id(request_id)

        start = time.perf_counter()
        response: Response = await call_next(request)  # type: ignore[operator]
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        log.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            client_ip=request.client.host if request.client else "unknown",
        )

        response.headers["X-Request-ID"] = request_id
        return response
