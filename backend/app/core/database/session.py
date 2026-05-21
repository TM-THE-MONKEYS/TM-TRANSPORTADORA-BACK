"""Async SQLAlchemy session factory — lazy initialization."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class _LazySessionFactory:
    """Lazy wrapper so the engine is not created at import time."""

    _factory: async_sessionmaker[AsyncSession] | None = None

    def _get_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._factory is None:
            from app.core.database.engine import get_engine

            self._factory = async_sessionmaker(
                bind=get_engine(),
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
        return self._factory

    def __call__(self) -> AsyncSession:
        return self._get_factory()()  # type: ignore[return-value]


AsyncSessionLocal = _LazySessionFactory()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    factory = AsyncSessionLocal._get_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
