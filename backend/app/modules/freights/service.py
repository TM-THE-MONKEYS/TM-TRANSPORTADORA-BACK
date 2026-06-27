"""Freight service."""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.freights.models import Freight, FreightCost, FreightStop
from app.modules.freights.repository import FreightRepository
from app.modules.freights.schemas import FreightCostCreate, FreightCreate, FreightStopCreate, FreightUpdate
from app.modules.users.models import User
from app.shared.enums import FreightStatus, UserRole
from app.shared.exceptions.custom import ForbiddenException, NotFoundException
from app.shared.pagination import PagedResponse, PageParams
from app.shared.security.resource_access import (
    assert_freight_read_access,
    resolve_freight_list_driver_filter,
)

log = structlog.get_logger(__name__)

_ALLOWED_TRANSITIONS: dict[FreightStatus, list[FreightStatus]] = {
    FreightStatus.ORCAMENTO: [FreightStatus.CONFIRMADO, FreightStatus.CANCELADO],
    FreightStatus.CONFIRMADO: [FreightStatus.EM_COLETA, FreightStatus.CANCELADO],
    FreightStatus.EM_COLETA: [FreightStatus.EM_TRANSPORTE, FreightStatus.CANCELADO],
    FreightStatus.EM_TRANSPORTE: [FreightStatus.ENTREGUE, FreightStatus.CANCELADO],
    FreightStatus.ENTREGUE: [],
    FreightStatus.CANCELADO: [],
}

_STATUS_FLOW: list[FreightStatus] = [
    FreightStatus.ORCAMENTO,
    FreightStatus.CONFIRMADO,
    FreightStatus.EM_COLETA,
    FreightStatus.EM_TRANSPORTE,
    FreightStatus.ENTREGUE,
]


class FreightService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._repo = FreightRepository(session, tenant_id)

    def _check_write_access(self, user: User) -> None:
        if user.role not in (UserRole.ADMIN, UserRole.OPERADOR):
            raise ForbiddenException("Acesso negado")

    async def create(self, data: FreightCreate, created_by: User) -> Freight:
        self._check_write_access(created_by)
        freight_data = data.model_dump(exclude={"costs", "paradas"})
        freight_data["origem"] = data.origem.model_dump()
        freight_data["destino"] = data.destino.model_dump()
        freight = Freight(**freight_data)
        freight = await self._repo.create(freight)
        if data.paradas:
            stops = [self._stop_from_payload(p) for p in data.paradas]
            saved_stops = await self._repo.add_stops(freight.id, stops)
            freight.stops = saved_stops
        for cost_data in data.costs:
            await self._repo.add_cost(freight.id, cost_data.tipo, cost_data.valor, cost_data.descricao)
        from app.modules.finance.freight_sync import ensure_freight_revenue

        await ensure_freight_revenue(self._session, freight)
        freight_id = freight.id
        await self._session.commit()
        self._session.expire(freight)
        freight = await self._repo.get_by_id(freight_id, with_relations=True)
        assert freight is not None
        log.info("freight_created", freight_id=str(freight.id), client_id=str(data.client_id))
        return freight

    @staticmethod
    def _stop_from_payload(parada: FreightStopCreate) -> FreightStop:
        return FreightStop(
            sequence=parada.ordem,
            cep=parada.cep,
            street=parada.logradouro,
            neighborhood=parada.bairro,
            city=parada.cidade,
            state=parada.estado.upper(),
            cargo_description=parada.observacoes,
            weight_kg=parada.peso_kg,
        )

    async def get_by_id(self, freight_id: uuid.UUID, requesting_user: User) -> Freight:
        freight = await self._repo.get_by_id(freight_id, with_relations=True)
        if not freight:
            raise NotFoundException("Frete não encontrado")
        await assert_freight_read_access(self._session, freight, requesting_user)
        return freight

    async def list(
        self,
        params: PageParams,
        requesting_user: User,
        status: FreightStatus | None = None,
        client_id: uuid.UUID | None = None,
        driver_id: uuid.UUID | None = None,
        truck_id: uuid.UUID | None = None,
    ) -> PagedResponse[Freight]:
        driver_id = await resolve_freight_list_driver_filter(
            self._session, requesting_user, driver_id
        )
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
        if data.status:
            await self._on_status_changed(freight, data.status)
        await self._session.commit()
        if data.status or data.model_dump(exclude_none=True):
            freight = await self._repo.get_by_id(freight_id, with_relations=True)
            assert freight is not None
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

    async def advance_status(self, freight_id: uuid.UUID, requesting_user: User) -> Freight:
        self._check_write_access(requesting_user)
        freight = await self._repo.get_by_id(freight_id)
        if not freight:
            raise NotFoundException("Frete não encontrado")
        try:
            idx = _STATUS_FLOW.index(freight.status)
        except ValueError:
            raise ForbiddenException(f"Status {freight.status.value} não pode ser avançado")
        if idx >= len(_STATUS_FLOW) - 1:
            raise ForbiddenException("Frete já está no status final")
        next_status = _STATUS_FLOW[idx + 1]
        freight.status = next_status
        freight = await self._repo.update(freight)
        await self._on_status_changed(freight, next_status)
        await self._session.commit()
        freight = await self._repo.get_by_id(freight_id, with_relations=True)
        assert freight is not None
        log.info("freight_status_advanced", freight_id=str(freight_id), new_status=next_status.value)
        return freight

    async def update_status(
        self, freight_id: uuid.UUID, new_status: FreightStatus, requesting_user: User
    ) -> Freight:
        self._check_write_access(requesting_user)
        freight = await self._repo.get_by_id(freight_id)
        if not freight:
            raise NotFoundException("Frete não encontrado")
        allowed = _ALLOWED_TRANSITIONS.get(freight.status, [])
        if new_status != freight.status and new_status not in allowed:
            raise ForbiddenException(
                f"Transição inválida: {freight.status.value} → {new_status.value}"
            )
        freight.status = new_status
        freight = await self._repo.update(freight)
        await self._on_status_changed(freight, new_status)
        await self._session.commit()
        freight = await self._repo.get_by_id(freight_id, with_relations=True)
        assert freight is not None
        log.info("freight_status_updated", freight_id=str(freight_id), new_status=new_status.value)
        return freight

    async def _on_status_changed(self, freight: Freight, new_status: FreightStatus) -> None:
        if new_status != FreightStatus.ENTREGUE:
            return
        from app.modules.finance.freight_sync import create_commission_expense

        await create_commission_expense(self._session, freight)

    async def list_costs(
        self, freight_id: uuid.UUID, requesting_user: User
    ) -> list[FreightCost]:
        freight = await self._repo.get_by_id(freight_id)
        if not freight:
            raise NotFoundException("Frete não encontrado")
        await assert_freight_read_access(self._session, freight, requesting_user)
        return await self._repo.list_costs_by_freight(freight_id)

    async def add_cost(self, freight_id: uuid.UUID, data: FreightCostCreate, added_by: User) -> FreightCost:
        self._check_write_access(added_by)
        freight = await self._repo.get_by_id(freight_id)
        if not freight:
            raise NotFoundException("Frete não encontrado")
        cost = await self._repo.add_cost(freight_id, data.tipo, data.valor, data.descricao)
        from app.modules.finance.freight_sync import create_cost_expense

        await create_cost_expense(self._session, cost)
        await self._session.commit()
        return cost
