"""Freight repository."""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.freights.models import Freight, FreightAttachment, FreightCost, FreightStop
from app.shared.base_repository import TenantBaseRepository
from app.shared.enums import FreightStatus
from app.shared.pagination import PageParams

log = structlog.get_logger(__name__)


class FreightRepository(TenantBaseRepository[Freight]):
    model = Freight

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        super().__init__(session, tenant_id)

    async def get_by_id(self, freight_id: uuid.UUID, with_relations: bool = False) -> Freight | None:
        query = self._base_query().where(Freight.id == freight_id)
        if with_relations:
            query = query.options(
                selectinload(Freight.costs),
                selectinload(Freight.attachments),
                selectinload(Freight.stops),
            )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def list(
        self,
        params: PageParams,
        status: FreightStatus | None = None,
        client_id: uuid.UUID | None = None,
        driver_id: uuid.UUID | None = None,
        truck_id: uuid.UUID | None = None,
    ) -> tuple[list[Freight], int]:
        query = self._base_query()
        if status:
            query = query.where(Freight.status == status)
        if client_id:
            query = query.where(Freight.client_id == client_id)
        if driver_id:
            query = query.where(Freight.driver_id == driver_id)
        if truck_id:
            query = query.where(Freight.truck_id == truck_id)
        total = await self._count(query)
        result = await self._session.execute(
            query.options(selectinload(Freight.stops))
            .order_by(Freight.created_at.desc())
            .offset(params.offset)
            .limit(params.limit)
        )
        return list(result.scalars().all()), total

    async def list_costs_by_freight(self, freight_id: uuid.UUID) -> list[FreightCost]:
        result = await self._session.execute(
            select(FreightCost)
            .where(
                FreightCost.freight_id == freight_id,
                FreightCost.tenant_id == self._tenant_id,
            )
            .order_by(FreightCost.created_at.desc())
        )
        return list(result.scalars().all())

    async def add_stops(self, freight_id: uuid.UUID, stops: list[FreightStop]) -> list[FreightStop]:
        for stop in stops:
            stop.freight_id = freight_id
            stop.tenant_id = self._tenant_id
            self._session.add(stop)
        await self._session.flush()
        return stops

    async def add_cost(self, freight_id: uuid.UUID, tipo: str, valor: float, descricao: str | None = None) -> FreightCost:
        cost = FreightCost(freight_id=freight_id, tipo=tipo, valor=valor, descricao=descricao, tenant_id=self._tenant_id)
        self._session.add(cost)
        await self._session.flush()
        return cost

    async def add_attachment(self, freight_id: uuid.UUID, file_url: str, tipo: str, descricao: str | None) -> FreightAttachment:
        att = FreightAttachment(freight_id=freight_id, file_url=file_url, tipo=tipo, descricao=descricao, tenant_id=self._tenant_id)
        self._session.add(att)
        await self._session.flush()
        return att

    async def count_by_status(self) -> dict[str, int]:
        result = await self._session.execute(
            select(Freight.status, func.count(Freight.id))
            .where(Freight.deleted_at.is_(None), Freight.tenant_id == self._tenant_id)
            .group_by(Freight.status)
        )
        return {row[0].value: row[1] for row in result.all()}

    async def revenue_sum(self, status: FreightStatus | None = None) -> float:
        query = select(func.sum(Freight.valor_frete)).where(
            Freight.deleted_at.is_(None), Freight.tenant_id == self._tenant_id
        )
        if status:
            query = query.where(Freight.status == status)
        result = await self._session.execute(query)
        return float(result.scalar_one() or 0.0)
