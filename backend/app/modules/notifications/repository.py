"""Notification repository."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import FreightNotification, NotificationRead


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, notification: FreightNotification
    ) -> FreightNotification:
        self._session.add(notification)
        await self._session.flush()
        await self._session.refresh(notification)
        return notification

    async def get_by_id(self, notification_id: uuid.UUID) -> FreightNotification | None:
        result = await self._session.execute(
            select(FreightNotification).where(
                FreightNotification.id == notification_id
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
                )
            )
        await self._session.flush()
        return len(unread_ids)

    def _base_query(self) -> object:
        return select(FreightNotification).order_by(
            FreightNotification.created_at.desc()
        )

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
                ~FreightNotification.id.in_(read_ids)
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
        count_query = select(func.count()).select_from(base.subquery())  # type: ignore[arg-type]
        total = (await self._session.execute(count_query)).scalar_one()
        unread_count = len(await self._get_unread_ids(user_id))

        query = base
        if unread_only:
            unread_ids = await self._get_unread_ids(user_id)
            if not unread_ids:
                return [], total, unread_count
            query = query.where(FreightNotification.id.in_(unread_ids))  # type: ignore[union-attr]

        result = await self._session.execute(
            query.offset(offset).limit(limit)  # type: ignore[union-attr]
        )
        notifications = list(result.scalars().all())
        read_set = await self._get_read_ids(user_id, [n.id for n in notifications])
        items = [(n, n.id in read_set) for n in notifications]
        return items, total, unread_count

    async def count_unread(self, user_id: uuid.UUID) -> int:
        return len(await self._get_unread_ids(user_id))
