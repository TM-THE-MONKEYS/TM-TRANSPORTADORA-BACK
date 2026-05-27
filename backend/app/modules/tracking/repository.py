"""Tracking repository."""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tracking.models import TrackingUpdate
from app.shared.base_repository import TenantBaseRepository

log = structlog.get_logger(__name__)


class TrackingRepository(TenantBaseRepository[TrackingUpdate]):
    model = TrackingUpdate

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        super().__init__(session, tenant_id)

    async def get_by_freight(self, freight_id: uuid.UUID) -> list[TrackingUpdate]:
        result = await self._session.execute(
            select(TrackingUpdate)
            .where(
                TrackingUpdate.freight_id == freight_id,
                TrackingUpdate.tenant_id == self._tenant_id,
            )
            .order_by(TrackingUpdate.evento_at.asc())
        )
        return list(result.scalars().all())

    async def get_latest(self, freight_id: uuid.UUID) -> TrackingUpdate | None:
        result = await self._session.execute(
            select(TrackingUpdate)
            .where(
                TrackingUpdate.freight_id == freight_id,
                TrackingUpdate.tenant_id == self._tenant_id,
            )
            .order_by(TrackingUpdate.evento_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
