"""Maintenance repository."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.maintenance.models import Maintenance
from app.shared.base_repository import TenantBaseRepository
from app.shared.enums import MaintenanceStatus, MaintenanceType
from app.shared.pagination import PageParams

log = structlog.get_logger(__name__)


class MaintenanceRepository(TenantBaseRepository[Maintenance]):
    model = Maintenance

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        super().__init__(session, tenant_id)

    async def list(
        self,
        params: PageParams,
        truck_id: uuid.UUID | None = None,
        status: MaintenanceStatus | None = None,
        tipo: MaintenanceType | None = None,
    ) -> tuple[list[Maintenance], int]:
        query = self._base_query()
        if truck_id:
            query = query.where(Maintenance.truck_id == truck_id)
        if status:
            query = query.where(Maintenance.status == status)
        if tipo:
            query = query.where(Maintenance.tipo == tipo)
        total = await self._count(query)
        result = await self._session.execute(
            query.order_by(Maintenance.created_at.desc()).offset(params.offset).limit(params.limit)
        )
        return list(result.scalars().all()), total

    async def get_upcoming_alerts(self, days_ahead: int = 30) -> list[Maintenance]:
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) + timedelta(days=days_ahead)
        result = await self._session.execute(
            select(Maintenance)
            .where(
                Maintenance.deleted_at.is_(None),
                Maintenance.tenant_id == self._tenant_id,
                Maintenance.status == MaintenanceStatus.AGENDADA,
                Maintenance.data_prevista <= cutoff,
            )
            .order_by(Maintenance.data_prevista)
        )
        return list(result.scalars().all())
