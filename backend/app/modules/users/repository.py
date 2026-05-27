"""User repository."""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from app.shared.base_repository import TenantBaseRepository
from app.shared.enums import UserRole
from app.shared.pagination import PageParams

log = structlog.get_logger(__name__)


class UserRepository(TenantBaseRepository[User]):
    model = User

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        super().__init__(session, tenant_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            self._base_query().where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        params: PageParams,
        role: UserRole | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[User], int]:
        query = self._base_query()
        if role:
            query = query.where(User.role == role)
        if is_active is not None:
            query = query.where(User.is_active == is_active)
        if search:
            term = f"%{search}%"
            query = query.where(
                (User.nome.ilike(term)) | (User.email.ilike(term))
            )

        total = await self._count(query)
        result = await self._session.execute(
            query.order_by(User.created_at.desc())
            .offset(params.offset)
            .limit(params.limit)
        )
        return list(result.scalars().all()), total

    async def exists_by_email(self, email: str, exclude_id: uuid.UUID | None = None) -> bool:
        query = select(User.id).where(
            User.email == email.lower(),
            User.deleted_at.is_(None),
            User.tenant_id == self._tenant_id,
        )
        if exclude_id:
            query = query.where(User.id != exclude_id)
        result = await self._session.execute(query)
        return result.scalar_one_or_none() is not None
