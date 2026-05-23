"""Fuel refill repository."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.fuel.models import FuelRefill
from app.shared.enums import ACTIVE_FREIGHT_STATUSES, FreightStatus


class FuelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, refill: FuelRefill) -> FuelRefill:
        self._session.add(refill)
        await self._session.flush()
        await self._session.refresh(refill)
        return refill

    async def get_by_id(self, refill_id: uuid.UUID) -> FuelRefill | None:
        result = await self._session.execute(
            select(FuelRefill).where(FuelRefill.id == refill_id)
        )
        return result.scalar_one_or_none()

    async def list_by_freight(
        self,
        freight_id: uuid.UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[FuelRefill], int]:
        base = select(FuelRefill).where(FuelRefill.freight_id == freight_id)
        count_q = select(func.count()).select_from(base.subquery())
        total = (await self._session.execute(count_q)).scalar_one()

        result = await self._session.execute(
            base.order_by(FuelRefill.data_abastecimento.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def summarize_freight(self, freight_id: uuid.UUID) -> tuple[float, float, int]:
        result = await self._session.execute(
            select(
                func.coalesce(func.sum(FuelRefill.litros), 0.0),
                func.coalesce(func.sum(FuelRefill.valor_total), 0.0),
                func.count(FuelRefill.id),
            ).where(FuelRefill.freight_id == freight_id)
        )
        row = result.one()
        return float(row[0]), float(row[1]), int(row[2])

    async def get_active_freight_for_driver_user(
        self, user_id: uuid.UUID
    ) -> uuid.UUID | None:
        from app.modules.drivers.models import Driver
        from app.modules.freights.models import Freight

        driver_result = await self._session.execute(
            select(Driver.id).where(Driver.user_id == user_id)
        )
        driver_id = driver_result.scalar_one_or_none()
        if not driver_id:
            return None

        freight_result = await self._session.execute(
            select(Freight.id)
            .where(
                Freight.driver_id == driver_id,
                Freight.status.in_(ACTIVE_FREIGHT_STATUSES),
                Freight.deleted_at.is_(None),
            )
            .order_by(Freight.updated_at.desc())
            .limit(1)
        )
        return freight_result.scalar_one_or_none()
