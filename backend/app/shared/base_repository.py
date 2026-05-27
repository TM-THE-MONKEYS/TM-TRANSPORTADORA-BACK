"""Base repository with automatic tenant_id scoping."""
from __future__ import annotations

import uuid
from typing import Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class TenantBaseRepository(Generic[T]):
    """Base repo that injects WHERE tenant_id = :tid on every query."""

    model: type[T]

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    def _base_query(self) -> Select:
        q = select(self.model).where(self.model.tenant_id == self._tenant_id)  # type: ignore[attr-defined]
        if hasattr(self.model, "deleted_at"):
            q = q.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        return q

    async def get_by_id(self, entity_id: uuid.UUID) -> T | None:
        result = await self._session.execute(
            self._base_query().where(self.model.id == entity_id)  # type: ignore[attr-defined]
        )
        return result.scalar_one_or_none()

    async def create(self, obj: T) -> T:
        obj.tenant_id = self._tenant_id  # type: ignore[attr-defined]
        self._session.add(obj)
        await self._session.flush()
        await self._session.refresh(obj)
        return obj

    async def update(self, obj: T) -> T:
        await self._session.flush()
        await self._session.refresh(obj)
        return obj

    async def soft_delete(self, obj: T) -> None:
        obj.soft_delete()  # type: ignore[attr-defined]
        await self._session.flush()

    async def _count(self, query: Select) -> int:
        count_q = select(func.count()).select_from(query.subquery())
        result = await self._session.execute(count_q)
        return result.scalar_one()
