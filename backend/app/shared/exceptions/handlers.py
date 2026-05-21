"""Global exception handlers for FastAPI."""
from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from jose import JWTError

from app.shared.exceptions.custom import AppException

log = structlog.get_logger()


def _make_json_safe(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable objects to strings."""
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_json_safe(i) for i in obj]
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    return str(obj)


def _error_response(status_code: int, detail: Any) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": _make_json_safe(detail)},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request, exc: AppException
    ) -> JSONResponse:
        log.warning(
            "app_exception",
            status_code=exc.status_code,
            detail=exc.detail,
            path=request.url.path,
        )
        return _error_response(exc.status_code, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = _make_json_safe(exc.errors())
        log.warning(
            "validation_error",
            errors=errors,
            path=request.url.path,
        )
        return _error_response(422, errors)

    @app.exception_handler(JWTError)
    async def jwt_exception_handler(
        request: Request, exc: JWTError
    ) -> JSONResponse:
        return _error_response(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        log.exception(
            "unhandled_exception",
            exc_type=type(exc).__name__,
            path=request.url.path,
        )
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Internal server error",
        )
