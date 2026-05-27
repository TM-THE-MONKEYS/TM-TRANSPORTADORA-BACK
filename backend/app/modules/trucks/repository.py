"""Truck repository."""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.trucks.models import Truck
from app.shared.base_repository import TenantBaseRepository
from app.shared.enums import TruckStatus
from app.shared.pagination import PageParams

log = structlog.get_logger(__name__)


class TruckRepository(TenantBaseRepository[Truck]):
    model = Truck

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        super().__init__(session, tenant_id)

    async def get_by_placa(self, placa: str) -> Truck | None:
        result = await self._session.execute(
            self._base_query().where(Truck.placa == placa.upper())
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
            query = query.where(Truck.status == status)
        if search:
            term = f"%{search}%"
            query = query.where(
                Truck.placa.ilike(term) | Truck.modelo.ilike(term) | Truck.marca.ilike(term)
            )
        total = await self._count(query)
        result = await self._session.execute(
            query.order_by(Truck.placa).offset(params.offset).limit(params.limit)
        )
        return list(result.scalars().all()), total

    async def count_by_status(self) -> dict[str, int]:
        result = await self._session.execute(
            select(Truck.status, func.count(Truck.id))
            .where(Truck.deleted_at.is_(None), Truck.tenant_id == self._tenant_id)
            .group_by(Truck.status)
        )
        return {row[0].value: row[1] for row in result.all()}
