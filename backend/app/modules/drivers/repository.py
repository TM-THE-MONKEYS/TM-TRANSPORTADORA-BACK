"""Driver repository."""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.drivers.models import Driver
from app.shared.enums import DriverStatus
from app.shared.pagination import PageParams

log = structlog.get_logger(__name__)


class DriverRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _base_query(self) -> object:
        return select(Driver).where(Driver.deleted_at.is_(None))

    async def get_by_id(self, driver_id: uuid.UUID) -> Driver | None:
        result = await self._session.execute(
            self._base_query().where(Driver.id == driver_id)  # type: ignore[union-attr]
        )
        return result.scalar_one_or_none()

    async def get_by_cpf(self, cpf: str) -> Driver | None:
        result = await self._session.execute(
            self._base_query().where(Driver.cpf == cpf)  # type: ignore[union-attr]
        )
        return result.scalar_one_or_none()

    async def get_by_cnh(self, cnh: str) -> Driver | None:
        result = await self._session.execute(
            self._base_query().where(Driver.cnh == cnh)  # type: ignore[union-attr]
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        params: PageParams,
        status: DriverStatus | None = None,
        search: str | None = None,
    ) -> tuple[list[Driver], int]:
        query = self._base_query()
        if status:
            query = query.where(Driver.status == status)  # type: ignore[union-attr]
        if search:
            term = f"%{search}%"
            query = query.where(  # type: ignore[union-attr]
                Driver.nome.ilike(term) | Driver.cpf.ilike(term) | Driver.cnh.ilike(term)
            )
        count = await self._session.execute(
            select(func.count()).select_from(query.subquery())  # type: ignore[arg-type]
        )
        total = count.scalar_one()
        result = await self._session.execute(
            query.order_by(Driver.nome).offset(params.offset).limit(params.limit)  # type: ignore[union-attr]
        )
        return list(result.scalars().all()), total

    async def create(self, driver: Driver) -> Driver:
        self._session.add(driver)
        await self._session.flush()
        await self._session.refresh(driver)
        return driver

    async def update(self, driver: Driver) -> Driver:
        await self._session.flush()
        await self._session.refresh(driver)
        return driver

    async def soft_delete(self, driver: Driver) -> None:
        driver.soft_delete()
        await self._session.flush()
