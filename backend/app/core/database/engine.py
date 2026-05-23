"""Async SQLAlchemy engine — singleton with LRU-cached settings."""
from __future__ import annotations

from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config.settings import get_settings


def _uses_transaction_pooler(url: str) -> bool:
    """Supabase transaction pooler (PgBouncer) breaks prepared statements."""
    lowered = url.lower()
    return "pooler.supabase.com" in lowered or ":6543" in lowered


def _pooler_engine_url(url: str) -> str:
    """Append SQLAlchemy/asyncpg params required for PgBouncer transaction mode."""
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("prepared_statement_cache_size", "0")
    return urlunparse(parsed._replace(query=urlencode(query)))


def _pooler_connect_args() -> dict[str, object]:
    # Unique statement names avoid DuplicatePreparedStatementError on PgBouncer.
    return {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
    }


@lru_cache(maxsize=1)
def _create_engine() -> AsyncEngine:
    settings = get_settings()
    url = settings.database_url_async
    pooler = _uses_transaction_pooler(url)
    if pooler:
        url = _pooler_engine_url(url)

    engine_kwargs: dict = {
        "echo": settings.is_development,
        "query_cache_size": 0 if pooler else 500,
    }

    if pooler:
        engine_kwargs["poolclass"] = NullPool
        engine_kwargs["connect_args"] = _pooler_connect_args()
    else:
        engine_kwargs.update(
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            pool_recycle=3600,
            pool_timeout=30,
        )

    return create_async_engine(url, **engine_kwargs)


def get_engine() -> AsyncEngine:
    return _create_engine()


async def dispose_engine() -> None:
    engine = _create_engine()
    await engine.dispose()
    _create_engine.cache_clear()
