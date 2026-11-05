"""Maintenance repository."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import extract, or_, select
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
        competencia_mes: int | None = None,
        competencia_ano: int | None = None,
    ) -> tuple[list[Maintenance], int]:
        query = self._base_query()
        if truck_id:
            query = query.where(Maintenance.truck_id == truck_id)
        if status:
            query = query.where(Maintenance.status == status)
        if tipo:
            query = query.where(Maintenance.tipo == tipo)
        if competencia_mes and competencia_ano:
            # Filtra por data_prevista → created_at (fallback)
            query = query.where(
                or_(
                    (
                        Maintenance.data_prevista.isnot(None)
                        & (extract("year", Maintenance.data_prevista) == competencia_ano)
                        & (extract("month", Maintenance.data_prevista) == competencia_mes)
                    ),
                    (
                        Maintenance.data_prevista.is_(None)
                        & (extract("year", Maintenance.created_at) == competencia_ano)
                        & (extract("month", Maintenance.created_at) == competencia_mes)
                    ),
                )
            )
        total = await self._count(query)
        result = await self._session.execute(
            query.order_by(Maintenance.created_at.desc()).offset(params.offset).limit(params.limit)
        )
        return list(result.scalars().all()), total

    async def get_upcoming_alerts(self, days_ahead: int = 30) -> list[Maintenance]:
        """Alertas por data_prevista OU por km_proxima (com margem)."""
        from datetime import timedelta

        from sqlalchemy.orm import aliased

        from app.core.config.settings import get_settings
        from app.modules.trucks.models import Truck

        cutoff = datetime.now(timezone.utc) + timedelta(days=days_ahead)
        margin = get_settings().maintenance_km_alert_margin
        truck = aliased(Truck)

        by_date = (
            Maintenance.deleted_at.is_(None)
            & (Maintenance.tenant_id == self._tenant_id)
            & (Maintenance.status == MaintenanceStatus.AGENDADA)
            & (Maintenance.data_prevista.isnot(None))
            & (Maintenance.data_prevista <= cutoff)
        )
        by_km = (
            Maintenance.deleted_at.is_(None)
            & (Maintenance.tenant_id == self._tenant_id)
            & (Maintenance.status == MaintenanceStatus.AGENDADA)
            & Maintenance.km_proxima.isnot(None)
            & truck.deleted_at.is_(None)
            & (truck.km_atual >= Maintenance.km_proxima - margin)
        )

        result = await self._session.execute(
            select(Maintenance)
            .outerjoin(truck, truck.id == Maintenance.truck_id)
            .where(or_(by_date, by_km))
            .order_by(Maintenance.data_prevista.nulls_last())
        )
        # Dedup por id (pode casar nos dois critérios).
        seen: set[uuid.UUID] = set()
        items: list[Maintenance] = []
        for row in result.scalars().all():
            if row.id in seen:
                continue
            seen.add(row.id)
            items.append(row)
        return items
