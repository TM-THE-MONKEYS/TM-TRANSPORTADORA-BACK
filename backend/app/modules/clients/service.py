"""Client service."""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client
from app.modules.clients.repository import ClientRepository
from app.modules.clients.schemas import ClientCreate, ClientUpdate
from app.modules.users.models import User
from app.shared.enums import UserRole
from app.shared.exceptions.custom import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.shared.pagination import PagedResponse, PageParams
from app.shared.security.resource_access import assert_catalog_read_access

log = structlog.get_logger(__name__)


class ClientService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ClientRepository(session)

    def _check_write_access(self, user: User) -> None:
        if user.role not in (UserRole.ADMIN, UserRole.OPERADOR):
            raise ForbiddenException("Acesso negado")

    async def create(self, data: ClientCreate, created_by: User) -> Client:
        self._check_write_access(created_by)
        if await self._repo.get_by_cpf_cnpj(data.cpf_cnpj):
            raise ConflictException("CPF/CNPJ já cadastrado")
        client_data = data.model_dump()
        if client_data.get("endereco"):
            client_data["endereco"] = data.endereco.model_dump() if data.endereco else None
        client = Client(**client_data)
        client = await self._repo.create(client)
        await self._session.commit()
        log.info("client_created", client_id=str(client.id))
        return client

    async def get_by_id(self, client_id: uuid.UUID, requesting_user: User) -> Client:
        assert_catalog_read_access(requesting_user)
        client = await self._repo.get_by_id(client_id)
        if not client:
            raise NotFoundException("Cliente não encontrado")
        return client

    async def list(
        self,
        params: PageParams,
        requesting_user: User,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> PagedResponse[Client]:
        assert_catalog_read_access(requesting_user)
        items, total = await self._repo.list(params, is_active, search)
        return PagedResponse.create(items, total, params)

    async def update(self, client_id: uuid.UUID, data: ClientUpdate, updated_by: User) -> Client:
        self._check_write_access(updated_by)
        client = await self.get_by_id(client_id, updated_by)
        update_data = data.model_dump(exclude_none=True)
        if "endereco" in update_data and data.endereco:
            update_data["endereco"] = data.endereco.model_dump()
        for field, value in update_data.items():
            setattr(client, field, value)
        client = await self._repo.update(client)
        await self._session.commit()
        return client

    async def delete(self, client_id: uuid.UUID, deleted_by: User) -> None:
        self._check_write_access(deleted_by)
        client = await self.get_by_id(client_id, deleted_by)
        await self._repo.soft_delete(client)
        await self._session.commit()
        log.info("client_deleted", client_id=str(client_id))
