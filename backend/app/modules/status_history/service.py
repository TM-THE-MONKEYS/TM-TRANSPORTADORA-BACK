"""Grava e lista mudanças de status."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.status_history.models import StatusHistory
from app.modules.status_history.repository import StatusHistoryRepository
from app.shared.enums import StatusChangeSource, StatusEntityType


class StatusHistoryService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self._tenant_id = tenant_id
        self._repo = StatusHistoryRepository(session, tenant_id)

    async def record(
        self,
        *,
        entity_type: StatusEntityType,
        entity_id: uuid.UUID,
        from_status: str | None,
        to_status: str,
        source: StatusChangeSource,
        user_id: uuid.UUID | None = None,
        motivo: str | None = None,
        changed_at: datetime | None = None,
    ) -> StatusHistory | None:
        if from_status == to_status:
            return None
        row = StatusHistory(
            entity_type=entity_type.value,
            entity_id=entity_id,
            from_status=from_status,
            to_status=to_status,
            changed_by_user_id=user_id,
            changed_at=changed_at or datetime.now(UTC),
            source=source.value,
            motivo=motivo,
            tenant_id=self._tenant_id,
        )
        return await self._repo.create(row)

    async def list_for_entity(
        self, entity_type: StatusEntityType, entity_id: uuid.UUID
    ) -> list[StatusHistory]:
        return await self._repo.list_for_entity(entity_type, entity_id)
