"""Custom application exceptions."""
from __future__ import annotations

from http import HTTPStatus


class AppException(Exception):
    """Base application exception."""

    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR.value
    detail: str = "Internal server error"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.__class__.detail
        super().__init__(self.detail)


class NotFoundException(AppException):
    status_code = HTTPStatus.NOT_FOUND.value
    detail = "Resource not found"


class ConflictException(AppException):
    status_code = HTTPStatus.CONFLICT.value
    detail = "Resource already exists"


class UnauthorizedException(AppException):
    status_code = HTTPStatus.UNAUTHORIZED.value
    detail = "Not authenticated"


class ForbiddenException(AppException):
    status_code = HTTPStatus.FORBIDDEN.value
    detail = "Access forbidden"


class ValidationException(AppException):
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY.value
    detail = "Validation error"


class BadRequestException(AppException):
    status_code = HTTPStatus.BAD_REQUEST.value
    detail = "Bad request"


class RateLimitException(AppException):
    status_code = HTTPStatus.TOO_MANY_REQUESTS.value
    detail = "Too many requests"
