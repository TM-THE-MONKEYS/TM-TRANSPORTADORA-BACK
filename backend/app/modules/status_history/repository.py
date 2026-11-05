"""Status history repository."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.status_history.models import StatusHistory
from app.shared.base_repository import TenantBaseRepository
from app.shared.enums import StatusEntityType


class StatusHistoryRepository(TenantBaseRepository[StatusHistory]):
    model = StatusHistory

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        super().__init__(session, tenant_id)

    async def list_for_entity(
        self, entity_type: StatusEntityType, entity_id: uuid.UUID
    ) -> list[StatusHistory]:
        result = await self._session.execute(
            self._base_query()
            .where(
                StatusHistory.entity_type == entity_type.value,
                StatusHistory.entity_id == entity_id,
            )
            .order_by(StatusHistory.changed_at.asc())
        )
        return list(result.scalars().all())
