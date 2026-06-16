"""Global exception handlers for FastAPI."""
from __future__ import annotations

import re
from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from jose import JWTError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.config.settings import get_settings
from app.shared.exceptions.custom import AppException

log = structlog.get_logger()

_SENSITIVE_FIELD_NAMES = frozenset({
    "password",
    "current_password",
    "new_password",
    "refresh_token",
    "token",
})


def _sanitize_validation_errors(errors: list[Any]) -> list[Any]:
    """Remove sensitive field values from Pydantic validation errors."""
    sanitized: list[Any] = []
    for error in errors:
        if not isinstance(error, dict):
            sanitized.append(error)
            continue
        clean = dict(error)
        loc = clean.get("loc", ())
        field_name = loc[-1] if loc else None
        if field_name in _SENSITIVE_FIELD_NAMES:
            clean.pop("input", None)
            if isinstance(clean.get("ctx"), dict):
                clean["ctx"] = {
                    k: v for k, v in clean["ctx"].items() if k not in _SENSITIVE_FIELD_NAMES
                }
        sanitized.append(clean)
    return sanitized

_DEV_ORIGIN_RE = re.compile(r"https?://(localhost|127\.0\.0\.1)(:\d+)?$")


def _make_json_safe(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable objects to strings."""
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_json_safe(i) for i in obj]
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    return str(obj)


def _cors_headers(request: Request) -> dict[str, str]:
    """CORS on error responses (middleware may not run when ASGI fails early)."""
    origin = request.headers.get("origin")
    if not origin:
        return {}
    settings = get_settings()
    if origin in settings.cors_origins or (
        settings.is_development and _DEV_ORIGIN_RE.fullmatch(origin)
    ):
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
    return {}


def _error_response(status_code: int, detail: Any, request: Request) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": _make_json_safe(detail)},
        headers=_cors_headers(request),
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
        return _error_response(exc.status_code, exc.detail, request)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = _sanitize_validation_errors(_make_json_safe(exc.errors()))
        log.warning(
            "validation_error",
            errors=errors,
            path=request.url.path,
        )
        return _error_response(422, errors, request)

    @app.exception_handler(JWTError)
    async def jwt_exception_handler(
        request: Request, exc: JWTError
    ) -> JSONResponse:
        return _error_response(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token", request)

    @app.exception_handler(IntegrityError)
    async def integrity_exception_handler(
        request: Request, exc: IntegrityError
    ) -> JSONResponse:
        message = str(exc.__cause__ or exc).lower()
        if "cpf" in message:
            detail = "CPF já cadastrado"
        elif "cnh" in message:
            detail = "CNH já cadastrada"
        elif "email" in message:
            detail = "Email já cadastrado"
        else:
            detail = "Registro duplicado"
        log.warning("integrity_error", detail=detail, path=request.url.path)
        return _error_response(status.HTTP_409_CONFLICT, detail, request)

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(
        request: Request, exc: SQLAlchemyError
    ) -> JSONResponse:
        log.error(
            "database_error",
            exc_type=type(exc).__name__,
            exc_message=str(exc.__cause__ or exc),
            path=request.url.path,
        )
        detail = "Banco de dados indisponível. Verifique DATABASE_URL no .env do backend."
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail,
            request,
        )

    @app.exception_handler(OSError)
    async def os_error_handler(request: Request, exc: OSError) -> JSONResponse:
        log.error(
            "database_connection_error",
            exc_type=type(exc).__name__,
            path=request.url.path,
        )
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Não foi possível conectar ao banco de dados. Verifique DATABASE_URL e a rede.",
            request,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        try:
            log.exception(
                "unhandled_exception",
                exc_type=type(exc).__name__,
                path=request.url.path,
            )
        except Exception:
            log.error(
                "unhandled_exception",
                exc_type=type(exc).__name__,
                path=request.url.path,
            )
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Internal server error",
            request,
        )
