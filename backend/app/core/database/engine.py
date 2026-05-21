"""Async SQLAlchemy engine — singleton with LRU-cached settings."""
from __future__ import annotations

from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config.settings import get_settings


@lru_cache(maxsize=1)
def _create_engine() -> AsyncEngine:
    """Create the engine once and cache it for the process lifetime."""
    settings = get_settings()
    return create_async_engine(
        settings.database_url_async,
        echo=settings.is_development,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,  # Recycle connections every hour
        pool_timeout=30,
    )


def get_engine() -> AsyncEngine:
    return _create_engine()


async def dispose_engine() -> None:
    engine = _create_engine()
    await engine.dispose()
    _create_engine.cache_clear()
