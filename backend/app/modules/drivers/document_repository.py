"""Driver document repository."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.drivers.models import DriverDocument
from app.shared.base_repository import TenantBaseRepository


class DriverDocumentRepository(TenantBaseRepository[DriverDocument]):
    model = DriverDocument

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        super().__init__(session, tenant_id)

    async def list_by_driver(self, driver_id: uuid.UUID) -> list[DriverDocument]:
        from sqlalchemy import select

        result = await self._session.execute(
            self._base_query()
            .where(DriverDocument.driver_id == driver_id)
            .order_by(DriverDocument.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_for_driver(
        self, document_id: uuid.UUID, driver_id: uuid.UUID
    ) -> DriverDocument | None:
        from sqlalchemy import select

        result = await self._session.execute(
            self._base_query().where(
                DriverDocument.id == document_id,
                DriverDocument.driver_id == driver_id,
            )
        )
        return result.scalar_one_or_none()
