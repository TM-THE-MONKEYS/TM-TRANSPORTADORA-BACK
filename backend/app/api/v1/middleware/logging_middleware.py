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

# Thresholds for ops triage (no OpenTelemetry stack — structured logs only).
_SLOW_MS = 500
_VERY_SLOW_MS = 1000


def _route_template(request: Request) -> str | None:
    route = request.scope.get("route")
    path_format = getattr(route, "path_format", None) or getattr(route, "path", None)
    return str(path_format) if path_format else None


def _slow_tier(duration_ms: float) -> str:
    if duration_ms >= _VERY_SLOW_MS:
        return "very_slow"
    if duration_ms >= _SLOW_MS:
        return "slow"
    return "ok"


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: object) -> Response:
        request_id = str(uuid.uuid4())
        set_request_id(request_id)

        start = time.perf_counter()
        response: Response = await call_next(request)  # type: ignore[operator]
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        route = _route_template(request)
        # Query *keys* only — never log values (tokens, filters with PII).
        query_keys = sorted({k for k in request.query_params.keys()}) or None

        log.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            route=route,
            status_code=response.status_code,
            duration_ms=duration_ms,
            slow_tier=_slow_tier(duration_ms),
            query_keys=query_keys,
            client_ip=request.client.host if request.client else "unknown",
        )

        if duration_ms >= _SLOW_MS:
            log.warning(
                "slow_request",
                method=request.method,
                path=request.url.path,
                route=route,
                status_code=response.status_code,
                duration_ms=duration_ms,
                slow_tier=_slow_tier(duration_ms),
                query_keys=query_keys,
                client_ip=request.client.host if request.client else "unknown",
            )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = str(duration_ms)
        return response
