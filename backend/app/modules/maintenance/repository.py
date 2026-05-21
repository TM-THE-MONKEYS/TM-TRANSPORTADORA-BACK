"""Maintenance repository."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.maintenance.models import Maintenance
from app.shared.enums import MaintenanceStatus, MaintenanceType
from app.shared.pagination import PageParams

log = structlog.get_logger(__name__)


class MaintenanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _base_query(self) -> object:
        return select(Maintenance).where(Maintenance.deleted_at.is_(None))

    async def get_by_id(self, maintenance_id: uuid.UUID) -> Maintenance | None:
        result = await self._session.execute(
            self._base_query().where(Maintenance.id == maintenance_id)  # type: ignore[union-attr]
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        params: PageParams,
        truck_id: uuid.UUID | None = None,
        status: MaintenanceStatus | None = None,
        tipo: MaintenanceType | None = None,
    ) -> tuple[list[Maintenance], int]:
        query = self._base_query()
        if truck_id:
            query = query.where(Maintenance.truck_id == truck_id)  # type: ignore[union-attr]
        if status:
            query = query.where(Maintenance.status == status)  # type: ignore[union-attr]
        if tipo:
            query = query.where(Maintenance.tipo == tipo)  # type: ignore[union-attr]
        count = await self._session.execute(
            select(func.count()).select_from(query.subquery())  # type: ignore[arg-type]
        )
        total = count.scalar_one()
        result = await self._session.execute(
            query.order_by(Maintenance.created_at.desc()).offset(params.offset).limit(params.limit)  # type: ignore[union-attr]
        )
        return list(result.scalars().all()), total

    async def get_upcoming_alerts(self, days_ahead: int = 30) -> list[Maintenance]:
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) + timedelta(days=days_ahead)
        result = await self._session.execute(
            select(Maintenance)
            .where(
                Maintenance.deleted_at.is_(None),
                Maintenance.status == MaintenanceStatus.AGENDADA,
                Maintenance.data_prevista <= cutoff,
            )
            .order_by(Maintenance.data_prevista)
        )
        return list(result.scalars().all())

    async def create(self, maintenance: Maintenance) -> Maintenance:
        self._session.add(maintenance)
        await self._session.flush()
        await self._session.refresh(maintenance)
        return maintenance

    async def update(self, maintenance: Maintenance) -> Maintenance:
        await self._session.flush()
        await self._session.refresh(maintenance)
        return maintenance

    async def soft_delete(self, maintenance: Maintenance) -> None:
        maintenance.soft_delete()
        await self._session.flush()
