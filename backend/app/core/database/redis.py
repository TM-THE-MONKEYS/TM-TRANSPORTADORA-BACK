"""Redis connection pool with LRU-cached client."""
from __future__ import annotations

from functools import lru_cache

from redis.asyncio import ConnectionPool, Redis

from app.core.config.settings import get_settings


@lru_cache(maxsize=1)
def _get_pool() -> ConnectionPool:
    """Create a single shared connection pool for the process lifetime."""
    settings = get_settings()
    return ConnectionPool.from_url(
        settings.redis_url,
        password=settings.redis_password or None,
        max_connections=20,
        decode_responses=True,
    )


def get_redis() -> Redis:
    """Return an async Redis client backed by the shared pool."""
    return Redis(connection_pool=_get_pool())


async def close_redis() -> None:
    """Close the connection pool (call on shutdown)."""
    pool = _get_pool()
    await pool.aclose()
    _get_pool.cache_clear()
