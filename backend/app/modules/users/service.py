"""User service."""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.password import hash_password
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate, UserUpdate
from app.shared.enums import UserRole
from app.shared.exceptions.custom import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.shared.pagination import PagedResponse, PageParams

log = structlog.get_logger(__name__)


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = UserRepository(session)

    async def create(self, data: UserCreate, created_by: User) -> User:
        if created_by.role != UserRole.ADMIN:
            raise ForbiddenException("Apenas admins podem criar usuários")

        if await self._repo.exists_by_email(data.email):
            raise ConflictException("Email já cadastrado")

        user = User(
            nome=data.nome,
            email=data.email.lower(),
            hashed_password=hash_password(data.password),
            role=data.role,
            is_active=data.is_active,
        )
        user = await self._repo.create(user)
        await self._session.commit()
        log.info("user_created", user_id=str(user.id), created_by=str(created_by.id))
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User:
        user = await self._repo.get_by_id(user_id)
        if not user:
            raise NotFoundException("Usuário não encontrado")
        return user

    async def list(
        self,
        params: PageParams,
        role: UserRole | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> PagedResponse[User]:
        items, total = await self._repo.list(params, role, is_active, search)
        return PagedResponse.create(items, total, params)

    async def update(
        self, user_id: uuid.UUID, data: UserUpdate, updated_by: User
    ) -> User:
        if updated_by.role != UserRole.ADMIN and updated_by.id != user_id:
            raise ForbiddenException("Acesso negado")

        user = await self.get_by_id(user_id)

        if data.email and data.email.lower() != user.email:
            if await self._repo.exists_by_email(data.email, exclude_id=user.id):
                raise ConflictException("Email já cadastrado")
            user.email = data.email.lower()

        if data.nome is not None:
            user.nome = data.nome
        if data.role is not None:
            if updated_by.role != UserRole.ADMIN:
                raise ForbiddenException("Apenas admins podem alterar roles")
            user.role = data.role
        if data.is_active is not None:
            if updated_by.role != UserRole.ADMIN:
                raise ForbiddenException("Apenas admins podem ativar/desativar usuários")
            user.is_active = data.is_active

        user = await self._repo.update(user)
        await self._session.commit()
        return user

    async def delete(self, user_id: uuid.UUID, deleted_by: User) -> None:
        if deleted_by.role != UserRole.ADMIN:
            raise ForbiddenException("Apenas admins podem remover usuários")
        if deleted_by.id == user_id:
            raise BadRequestException("Não é possível remover a si mesmo")  # type: ignore[name-defined]

        user = await self.get_by_id(user_id)
        await self._repo.soft_delete(user)
        await self._session.commit()
        log.info("user_deleted", user_id=str(user_id), deleted_by=str(deleted_by.id))
