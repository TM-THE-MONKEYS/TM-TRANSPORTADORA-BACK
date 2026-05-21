"""Client repository."""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client
from app.shared.pagination import PageParams

log = structlog.get_logger(__name__)


class ClientRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _base_query(self) -> object:
        return select(Client).where(Client.deleted_at.is_(None))

    async def get_by_id(self, client_id: uuid.UUID) -> Client | None:
        result = await self._session.execute(
            self._base_query().where(Client.id == client_id)  # type: ignore[union-attr]
        )
        return result.scalar_one_or_none()

    async def get_by_cpf_cnpj(self, cpf_cnpj: str) -> Client | None:
        result = await self._session.execute(
            self._base_query().where(Client.cpf_cnpj == cpf_cnpj)  # type: ignore[union-attr]
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
            query = query.where(Client.is_active == is_active)  # type: ignore[union-attr]
        if search:
            term = f"%{search}%"
            query = query.where(  # type: ignore[union-attr]
                Client.nome.ilike(term) | Client.cpf_cnpj.ilike(term)
            )
        count = await self._session.execute(
            select(func.count()).select_from(query.subquery())  # type: ignore[arg-type]
        )
        total = count.scalar_one()
        result = await self._session.execute(
            query.order_by(Client.nome).offset(params.offset).limit(params.limit)  # type: ignore[union-attr]
        )
        return list(result.scalars().all()), total

    async def create(self, client: Client) -> Client:
        self._session.add(client)
        await self._session.flush()
        await self._session.refresh(client)
        return client

    async def update(self, client: Client) -> Client:
        await self._session.flush()
        await self._session.refresh(client)
        return client

    async def soft_delete(self, client: Client) -> None:
        client.soft_delete()
        await self._session.flush()
