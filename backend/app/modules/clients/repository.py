"""Client repository."""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client
from app.shared.base_repository import TenantBaseRepository
from app.shared.pagination import PageParams

log = structlog.get_logger(__name__)


class ClientRepository(TenantBaseRepository[Client]):
    model = Client

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        super().__init__(session, tenant_id)

    async def get_by_cpf_cnpj(self, cpf_cnpj: str) -> Client | None:
        result = await self._session.execute(
            self._base_query().where(Client.cpf_cnpj == cpf_cnpj)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        params: PageParams,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[Client], int]:
        query = self._base_query()
        if is_active is not None:
            query = query.where(Client.is_active == is_active)
        if search:
            term = f"%{search}%"
            query = query.where(
                Client.nome.ilike(term) | Client.cpf_cnpj.ilike(term)
            )
        total = await self._count(query)
        result = await self._session.execute(
            query.order_by(Client.nome).offset(params.offset).limit(params.limit)
        )
        return list(result.scalars().all()), total
