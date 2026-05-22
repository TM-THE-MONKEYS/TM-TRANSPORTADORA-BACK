"""Async SQLAlchemy engine — singleton with LRU-cached settings."""
from __future__ import annotations

import uuid
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config.settings import get_settings


def _unique_stmt_name() -> str:
    """Unique prepared-statement name per call — required for Supabase transaction pooler."""
    return f"_sa_{uuid.uuid4().hex}"


@lru_cache(maxsize=1)
def _create_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.database_url_async,
        echo=settings.is_development,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        pool_timeout=30,
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_name_func": _unique_stmt_name,
        },
    )


def get_engine() -> AsyncEngine:
    return _create_engine()


async def dispose_engine() -> None:
    engine = _create_engine()
    await engine.dispose()
    _create_engine.cache_clear()
