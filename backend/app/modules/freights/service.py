"""Freight service."""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.freights.models import Freight, FreightCost
from app.modules.freights.repository import FreightRepository
from app.modules.freights.schemas import FreightCostCreate, FreightCreate, FreightUpdate
from app.modules.users.models import User
from app.shared.enums import FreightStatus, UserRole
from app.shared.exceptions.custom import ForbiddenException, NotFoundException
from app.shared.pagination import PagedResponse, PageParams

log = structlog.get_logger(__name__)

_ALLOWED_TRANSITIONS: dict[FreightStatus, list[FreightStatus]] = {
    FreightStatus.ORCAMENTO: [FreightStatus.CONFIRMADO, FreightStatus.CANCELADO],
    FreightStatus.CONFIRMADO: [FreightStatus.EM_COLETA, FreightStatus.CANCELADO],
    FreightStatus.EM_COLETA: [FreightStatus.EM_TRANSPORTE, FreightStatus.CANCELADO],
    FreightStatus.EM_TRANSPORTE: [FreightStatus.ENTREGUE, FreightStatus.CANCELADO],
    FreightStatus.ENTREGUE: [],
    FreightStatus.CANCELADO: [],
}


class FreightService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = FreightRepository(session)

    def _check_write_access(self, user: User) -> None:
        if user.role not in (UserRole.ADMIN, UserRole.OPERADOR):
            raise ForbiddenException("Acesso negado")

    async def create(self, data: FreightCreate, created_by: User) -> Freight:
        self._check_write_access(created_by)
        freight_data = data.model_dump(exclude={"costs"})
        freight_data["origem"] = data.origem.model_dump()
        freight_data["destino"] = data.destino.model_dump()
        freight = Freight(**freight_data)
        freight = await self._repo.create(freight)
        for cost_data in data.costs:
            await self._repo.add_cost(freight.id, cost_data.tipo, cost_data.valor, cost_data.descricao)
        await self._session.commit()
        log.info("freight_created", freight_id=str(freight.id), client_id=str(data.client_id))
        return freight

    async def get_by_id(self, freight_id: uuid.UUID) -> Freight:
        freight = await self._repo.get_by_id(freight_id, with_relations=True)
        if not freight:
            raise NotFoundException("Frete não encontrado")
        return freight

    async def list(
        self,
        params: PageParams,
        status: FreightStatus | None = None,
        client_id: uuid.UUID | None = None,
        driver_id: uuid.UUID | None = None,
        truck_id: uuid.UUID | None = None,
    ) -> PagedResponse[Freight]:
        items, total = await self._repo.list(params, status, client_id, driver_id, truck_id)
        return PagedResponse.create(items, total, params)

    async def update(self, freight_id: uuid.UUID, data: FreightUpdate, updated_by: User) -> Freight:
        self._check_write_access(updated_by)
        freight = await self._repo.get_by_id(freight_id)
        if not freight:
            raise NotFoundException("Frete não encontrado")
        if data.status and data.status != freight.status:
            allowed = _ALLOWED_TRANSITIONS.get(freight.status, [])
            if data.status not in allowed:
                raise ForbiddenException(
                    f"Transição inválida: {freight.status.value} → {data.status.value}"
                )
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(freight, field, value)
        freight = await self._repo.update(freight)
        await self._session.commit()
        return freight

    async def delete(self, freight_id: uuid.UUID, deleted_by: User) -> None:
        self._check_write_access(deleted_by)
        freight = await self._repo.get_by_id(freight_id)
        if not freight:
            raise NotFoundException("Frete não encontrado")
        if freight.status not in (FreightStatus.ORCAMENTO, FreightStatus.CANCELADO):
            raise ForbiddenException("Apenas fretes em orçamento ou cancelados podem ser removidos")
        await self._repo.soft_delete(freight)
        await self._session.commit()

    async def add_cost(self, freight_id: uuid.UUID, data: FreightCostCreate, added_by: User) -> FreightCost:
        self._check_write_access(added_by)
        freight = await self._repo.get_by_id(freight_id)
        if not freight:
            raise NotFoundException("Frete não encontrado")
        cost = await self._repo.add_cost(freight_id, data.tipo, data.valor, data.descricao)
        await self._session.commit()
        return cost
