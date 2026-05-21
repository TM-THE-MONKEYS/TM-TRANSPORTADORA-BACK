"""User repository."""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from app.shared.enums import UserRole
from app.shared.pagination import PageParams

log = structlog.get_logger(__name__)


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _active_query(self) -> object:
        return select(User).where(User.deleted_at.is_(None))

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self._session.execute(
            self._active_query().where(User.id == user_id)  # type: ignore[union-attr]
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            self._active_query().where(User.email == email.lower())  # type: ignore[union-attr]
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        params: PageParams,
        role: UserRole | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[User], int]:
        query = self._active_query()
        if role:
            query = query.where(User.role == role)  # type: ignore[union-attr]
        if is_active is not None:
            query = query.where(User.is_active == is_active)  # type: ignore[union-attr]
        if search:
            term = f"%{search}%"
            query = query.where(  # type: ignore[union-attr]
                (User.nome.ilike(term)) | (User.email.ilike(term))
            )

        count_result = await self._session.execute(
            select(func.count()).select_from(query.subquery())  # type: ignore[arg-type]
        )
        total = count_result.scalar_one()

        result = await self._session.execute(
            query.order_by(User.created_at.desc())  # type: ignore[union-attr]
            .offset(params.offset)
            .limit(params.limit)
        )
        return list(result.scalars().all()), total

    async def create(self, user: User) -> User:
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def update(self, user: User) -> User:
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def soft_delete(self, user: User) -> None:
        user.soft_delete()
        await self._session.flush()

    async def exists_by_email(self, email: str, exclude_id: uuid.UUID | None = None) -> bool:
        query = select(User.id).where(
            User.email == email.lower(),
            User.deleted_at.is_(None),
        )
        if exclude_id:
            query = query.where(User.id != exclude_id)
        result = await self._session.execute(query)
        return result.scalar_one_or_none() is not None
