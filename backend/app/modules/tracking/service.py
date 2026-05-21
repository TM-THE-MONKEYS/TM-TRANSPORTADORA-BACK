"""Tracking service."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tracking.models import TrackingUpdate
from app.modules.tracking.repository import TrackingRepository
from app.modules.tracking.schemas import TrackingTimelineResponse, TrackingUpdateCreate
from app.modules.users.models import User
from app.shared.enums import UserRole
from app.shared.exceptions.custom import ForbiddenException

log = structlog.get_logger(__name__)


class TrackingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = TrackingRepository(session)

    def _check_write_access(self, user: User) -> None:
        if user.role not in (UserRole.ADMIN, UserRole.OPERADOR, UserRole.MOTORISTA):
            raise ForbiddenException("Acesso negado")

    async def add_update(self, data: TrackingUpdateCreate, added_by: User) -> TrackingUpdate:
        self._check_write_access(added_by)
        tracking = TrackingUpdate(
            freight_id=data.freight_id,
            status=data.status,
            descricao=data.descricao,
            latitude=data.latitude,
            longitude=data.longitude,
            cidade=data.cidade,
            estado=data.estado,
            evento_at=data.evento_at or datetime.now(timezone.utc),
        )
        tracking = await self._repo.create(tracking)
        await self._session.commit()
        log.info("tracking_update_added", freight_id=str(data.freight_id), status=data.status.value)
        return tracking

    async def get_timeline(self, freight_id: uuid.UUID) -> TrackingTimelineResponse:
        updates = await self._repo.get_by_freight(freight_id)
        latest = updates[-1] if updates else None
        return TrackingTimelineResponse(
            freight_id=freight_id,
            updates=updates,  # type: ignore[arg-type]
            current_status=latest.status if latest else None,
        )
