"""Truck implement repository."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.trucks.models import TruckImplement
from app.shared.base_repository import TenantBaseRepository


class TruckImplementRepository(TenantBaseRepository[TruckImplement]):
    model = TruckImplement

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        super().__init__(session, tenant_id)

    async def list_by_truck(self, truck_id: uuid.UUID) -> list[TruckImplement]:
        result = await self._session.execute(
            self._base_query()
            .where(TruckImplement.truck_id == truck_id)
            .order_by(TruckImplement.nome)
        )
        return list(result.scalars().all())

    async def get_by_id_for_truck(
        self, implement_id: uuid.UUID, truck_id: uuid.UUID
    ) -> TruckImplement | None:
        result = await self._session.execute(
            self._base_query().where(
                TruckImplement.id == implement_id,
                TruckImplement.truck_id == truck_id,
            )
        )
        return result.scalar_one_or_none()

    async def exists_placa_for_truck(
        self, truck_id: uuid.UUID, placa: str, exclude_id: uuid.UUID | None = None
    ) -> bool:
        query = self._base_query().where(
            TruckImplement.truck_id == truck_id,
            TruckImplement.placa == placa.upper(),
        )
        if exclude_id:
            query = query.where(TruckImplement.id != exclude_id)
        result = await self._session.execute(query.limit(1))
        return result.scalar_one_or_none() is not None
