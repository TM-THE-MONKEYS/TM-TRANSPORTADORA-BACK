"""Freight repository."""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.freights.models import Freight, FreightAttachment, FreightCost
from app.shared.enums import FreightStatus
from app.shared.pagination import PageParams

log = structlog.get_logger(__name__)


class FreightRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _base_query(self) -> object:
        return select(Freight).where(Freight.deleted_at.is_(None))

    async def get_by_id(self, freight_id: uuid.UUID, with_relations: bool = False) -> Freight | None:
        query = self._base_query().where(Freight.id == freight_id)  # type: ignore[union-attr]
        if with_relations:
            query = query.options(  # type: ignore[union-attr]
                selectinload(Freight.costs),
                selectinload(Freight.attachments),
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
            query = query.where(Freight.status == status)  # type: ignore[union-attr]
        if client_id:
            query = query.where(Freight.client_id == client_id)  # type: ignore[union-attr]
        if driver_id:
            query = query.where(Freight.driver_id == driver_id)  # type: ignore[union-attr]
        if truck_id:
            query = query.where(Freight.truck_id == truck_id)  # type: ignore[union-attr]
        count = await self._session.execute(
            select(func.count()).select_from(query.subquery())  # type: ignore[arg-type]
        )
        total = count.scalar_one()
        result = await self._session.execute(
            query.order_by(Freight.created_at.desc()).offset(params.offset).limit(params.limit)  # type: ignore[union-attr]
        )
        return list(result.scalars().all()), total

    async def create(self, freight: Freight) -> Freight:
        self._session.add(freight)
        await self._session.flush()
        await self._session.refresh(freight)
        return freight

    async def update(self, freight: Freight) -> Freight:
        await self._session.flush()
        await self._session.refresh(freight)
        return freight

    async def soft_delete(self, freight: Freight) -> None:
        freight.soft_delete()
        await self._session.flush()

    async def add_cost(self, freight_id: uuid.UUID, tipo: str, valor: float, descricao: str | None = None) -> FreightCost:
        cost = FreightCost(freight_id=freight_id, tipo=tipo, valor=valor, descricao=descricao)
        self._session.add(cost)
        await self._session.flush()
        return cost

    async def add_attachment(self, freight_id: uuid.UUID, file_url: str, tipo: str, descricao: str | None) -> FreightAttachment:
        att = FreightAttachment(freight_id=freight_id, file_url=file_url, tipo=tipo, descricao=descricao)
        self._session.add(att)
        await self._session.flush()
        return att

    async def count_by_status(self) -> dict[str, int]:
        result = await self._session.execute(
            select(Freight.status, func.count(Freight.id))
            .where(Freight.deleted_at.is_(None))
            .group_by(Freight.status)
        )
        return {row[0].value: row[1] for row in result.all()}

    async def revenue_sum(self, status: FreightStatus | None = None) -> float:
        query = select(func.sum(Freight.valor_frete)).where(Freight.deleted_at.is_(None))
        if status:
            query = query.where(Freight.status == status)
        result = await self._session.execute(query)
        return float(result.scalar_one() or 0.0)
