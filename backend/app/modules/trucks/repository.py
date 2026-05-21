"""Truck repository."""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.trucks.models import Truck
from app.shared.enums import TruckStatus
from app.shared.pagination import PageParams

log = structlog.get_logger(__name__)


class TruckRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _base_query(self) -> object:
        return select(Truck).where(Truck.deleted_at.is_(None))

    async def get_by_id(self, truck_id: uuid.UUID) -> Truck | None:
        result = await self._session.execute(
            self._base_query().where(Truck.id == truck_id)  # type: ignore[union-attr]
        )
        return result.scalar_one_or_none()

    async def get_by_placa(self, placa: str) -> Truck | None:
        result = await self._session.execute(
            self._base_query().where(Truck.placa == placa.upper())  # type: ignore[union-attr]
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        params: PageParams,
        status: TruckStatus | None = None,
        search: str | None = None,
    ) -> tuple[list[Truck], int]:
        query = self._base_query()
        if status:
            query = query.where(Truck.status == status)  # type: ignore[union-attr]
        if search:
            term = f"%{search}%"
            query = query.where(  # type: ignore[union-attr]
                Truck.placa.ilike(term) | Truck.modelo.ilike(term) | Truck.marca.ilike(term)
            )
        count = await self._session.execute(
            select(func.count()).select_from(query.subquery())  # type: ignore[arg-type]
        )
        total = count.scalar_one()
        result = await self._session.execute(
            query.order_by(Truck.placa).offset(params.offset).limit(params.limit)  # type: ignore[union-attr]
        )
        return list(result.scalars().all()), total

    async def create(self, truck: Truck) -> Truck:
        self._session.add(truck)
        await self._session.flush()
        await self._session.refresh(truck)
        return truck

    async def update(self, truck: Truck) -> Truck:
        await self._session.flush()
        await self._session.refresh(truck)
        return truck

    async def soft_delete(self, truck: Truck) -> None:
        truck.soft_delete()
        await self._session.flush()

    async def count_by_status(self) -> dict[str, int]:
        result = await self._session.execute(
            select(Truck.status, func.count(Truck.id))
            .where(Truck.deleted_at.is_(None))
            .group_by(Truck.status)
        )
        return {row[0].value: row[1] for row in result.all()}
