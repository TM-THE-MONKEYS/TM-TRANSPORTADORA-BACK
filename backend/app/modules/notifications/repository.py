"""Notification repository."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import FreightNotification, NotificationRead
from app.shared.base_repository import TenantBaseRepository


class NotificationRepository(TenantBaseRepository[FreightNotification]):
    model = FreightNotification

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        super().__init__(session, tenant_id)

    def _base_query(self) -> Select:
        return (
            select(FreightNotification)
            .where(FreightNotification.tenant_id == self._tenant_id)
            .order_by(FreightNotification.created_at.desc())
        )

    async def get_by_id(self, notification_id: uuid.UUID) -> FreightNotification | None:
        result = await self._session.execute(
            select(FreightNotification).where(
                FreightNotification.id == notification_id,
                FreightNotification.tenant_id == self._tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def mark_read(
        self, notification_id: uuid.UUID, user_id: uuid.UUID
    ) -> NotificationRead | None:
        existing = await self._session.execute(
            select(NotificationRead).where(
                NotificationRead.notification_id == notification_id,
                NotificationRead.user_id == user_id,
            )
        )
        if existing.scalar_one_or_none():
            return None

        read = NotificationRead(
            notification_id=notification_id,
            user_id=user_id,
            read_at=datetime.now(timezone.utc),
            tenant_id=self._tenant_id,
        )
        self._session.add(read)
        await self._session.flush()
        return read

    async def mark_all_read(self, user_id: uuid.UUID) -> int:
        unread_ids = await self._get_unread_ids(user_id)
        now = datetime.now(timezone.utc)
        for nid in unread_ids:
            self._session.add(
                NotificationRead(
                    notification_id=nid,
                    user_id=user_id,
                    read_at=now,
                    tenant_id=self._tenant_id,
                )
            )
        await self._session.flush()
        return len(unread_ids)

    async def _get_read_ids(
        self, user_id: uuid.UUID, notification_ids: list[uuid.UUID]
    ) -> set[uuid.UUID]:
        if not notification_ids:
            return set()
        result = await self._session.execute(
            select(NotificationRead.notification_id).where(
                NotificationRead.user_id == user_id,
                NotificationRead.notification_id.in_(notification_ids),
            )
        )
        return {row[0] for row in result.all()}

    async def _get_unread_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        read_ids = select(NotificationRead.notification_id).where(
            NotificationRead.user_id == user_id
        )
        result = await self._session.execute(
            select(FreightNotification.id).where(
                FreightNotification.tenant_id == self._tenant_id,
                ~FreightNotification.id.in_(read_ids),
            )
        )
        return [row[0] for row in result.all()]

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        unread_only: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[tuple[FreightNotification, bool]], int, int]:
        base = self._base_query()
        total = await self._count(base)
        unread_count = len(await self._get_unread_ids(user_id))

        query = base
        if unread_only:
            unread_ids = await self._get_unread_ids(user_id)
            if not unread_ids:
                return [], total, unread_count
            query = query.where(FreightNotification.id.in_(unread_ids))

        result = await self._session.execute(
            query.offset(offset).limit(limit)
        )
        notifications = list(result.scalars().all())
        read_set = await self._get_read_ids(user_id, [n.id for n in notifications])
        items = [(n, n.id in read_set) for n in notifications]
        return items, total, unread_count

    async def count_unread(self, user_id: uuid.UUID) -> int:
        return len(await self._get_unread_ids(user_id))
