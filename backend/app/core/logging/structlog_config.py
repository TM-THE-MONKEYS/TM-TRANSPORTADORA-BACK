"""Structlog configuration with structured JSON output and request context."""
from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog

_request_id_var: ContextVar[str] = ContextVar("request_id", default="")
_user_id_var: ContextVar[str] = ContextVar("user_id", default="")


def get_request_id() -> str:
    return _request_id_var.get()


def set_request_id(request_id: str) -> None:
    _request_id_var.set(request_id)


def get_user_id() -> str:
    return _user_id_var.get()


def set_user_id(user_id: str) -> None:
    _user_id_var.set(user_id)


def _add_request_context(
    logger: Any, method: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    request_id = get_request_id()
    user_id = get_user_id()
    if request_id:
        event_dict["request_id"] = request_id
    if user_id:
        event_dict["user_id"] = user_id
    return event_dict


def configure_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        _add_request_context,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if log_format == "json":
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    for noisy in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
