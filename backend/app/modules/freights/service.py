"""Freight service."""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.freights.models import Freight, FreightCost, FreightStop
from app.modules.freights.repository import FreightRepository
from app.modules.freights.schemas import FreightCostCreate, FreightCreate, FreightStopCreate, FreightUpdate
from app.modules.users.models import User
from app.shared.enums import FreightStatus, UserRole
from app.shared.exceptions.custom import BadRequestException, ForbiddenException, NotFoundException
from app.shared.pagination import PagedResponse, PageParams
from app.shared.security.resource_access import (
    assert_freight_read_access,
    resolve_freight_list_driver_filter,
)

log = structlog.get_logger(__name__)

# Fluxo simplificado: em_transporte → entregue, cancelado a partir de qualquer status.
# Status legados (orcamento/confirmado/em_coleta) existem só em dados antigos — aceitos
# como estado atual, mas nenhum frete pode voltar para eles.
_LEGACY_STATUSES: frozenset[FreightStatus] = frozenset(
    {FreightStatus.ORCAMENTO, FreightStatus.CONFIRMADO, FreightStatus.EM_COLETA}
)


def _is_valid_status_transition(current: FreightStatus, target: FreightStatus) -> bool:
    """Qualquer transição entre em_transporte/entregue/cancelado; legado só como origem."""
    if current == target:
        return True
    return target not in _LEGACY_STATUSES


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
        from app.modules.finance.freight_sync import create_cost_expense, ensure_freight_revenue, is_fuel_cost_tipo

        for cost_data in data.costs:
            if is_fuel_cost_tipo(cost_data.tipo):
                raise BadRequestException(
                    "Registre combustível pela tela de Abastecimento para evitar duplicidade no financeiro"
                )
            cost = await self._repo.add_cost(
                freight.id, cost_data.tipo, cost_data.valor, cost_data.descricao
            )
            await create_cost_expense(self._session, cost)
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
            if not _is_valid_status_transition(freight.status, data.status):
                raise ForbiddenException(
                    f"Transição inválida: {freight.status.value} → {data.status.value}"
                )
        old_status = freight.status
        updated_fields = data.model_dump(exclude_none=True)
        for field, value in updated_fields.items():
            setattr(freight, field, value)
        freight = await self._repo.update(freight)
        if "valor_frete" in updated_fields or "data_entrega_prevista" in updated_fields:
            from app.modules.finance.freight_sync import ensure_freight_revenue

            await ensure_freight_revenue(self._session, freight)
        if data.status and data.status != old_status:
            await self._on_status_changed(freight, old_status, data.status)
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
        if deleted_by.role != UserRole.ADMIN and freight.status not in (
            FreightStatus.ORCAMENTO,
            FreightStatus.CANCELADO,
        ):
            raise ForbiddenException(
                "Apenas fretes em orçamento ou cancelados podem ser removidos. "
                "Administradores podem excluir fretes em qualquer status."
            )
        removed_entries = await self._soft_delete_linked_finance_entries(freight_id)
        await self._repo.soft_delete(freight)
        await self._session.commit()
        log.info(
            "freight_deleted",
            freight_id=str(freight_id),
            finance_entries_removed=removed_entries,
        )

    async def _soft_delete_linked_finance_entries(self, freight_id: uuid.UUID) -> int:
        """Exclui (soft) receitas/despesas em tm_finance_entries vinculadas ao frete."""
        from app.modules.finance.models import FinanceEntry

        result = await self._session.execute(
            select(FinanceEntry).where(
                FinanceEntry.freight_id == freight_id,
                FinanceEntry.tenant_id == self._tenant_id,
                FinanceEntry.deleted_at.is_(None),
            )
        )
        entries = list(result.scalars().all())
        for entry in entries:
            entry.soft_delete()
        await self._session.flush()
        return len(entries)

    async def advance_status(self, freight_id: uuid.UUID, requesting_user: User) -> Freight:
        self._check_write_access(requesting_user)
        freight = await self._repo.get_by_id(freight_id)
        if not freight:
            raise NotFoundException("Frete não encontrado")
        if freight.status in _LEGACY_STATUSES:
            next_status = FreightStatus.EM_TRANSPORTE
        elif freight.status == FreightStatus.EM_TRANSPORTE:
            next_status = FreightStatus.ENTREGUE
        else:
            raise ForbiddenException("Frete já está no status final")
        old_status = freight.status
        freight.status = next_status
        freight = await self._repo.update(freight)
        await self._on_status_changed(freight, old_status, next_status)
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
        if new_status != freight.status and not _is_valid_status_transition(
            freight.status, new_status
        ):
            raise ForbiddenException(
                f"Transição inválida: {freight.status.value} → {new_status.value}"
            )
        old_status = freight.status
        freight.status = new_status
        freight = await self._repo.update(freight)
        if new_status != old_status:
            await self._on_status_changed(freight, old_status, new_status)
        await self._session.commit()
        freight = await self._repo.get_by_id(freight_id, with_relations=True)
        assert freight is not None
        log.info("freight_status_updated", freight_id=str(freight_id), new_status=new_status.value)
        return freight

    async def _on_status_changed(
        self,
        freight: Freight,
        old_status: FreightStatus,
        new_status: FreightStatus,
    ) -> None:
        from app.modules.finance.freight_sync import (
            cancel_commission_expense,
            cancel_freight_revenue,
            create_commission_expense,
            reactivate_freight_revenue,
        )

        if old_status == FreightStatus.ENTREGUE and new_status != FreightStatus.ENTREGUE:
            await cancel_commission_expense(self._session, freight)
        if new_status == FreightStatus.ENTREGUE:
            await create_commission_expense(self._session, freight)
        if new_status == FreightStatus.CANCELADO:
            await cancel_freight_revenue(self._session, freight)
        elif old_status == FreightStatus.CANCELADO:
            await reactivate_freight_revenue(self._session, freight)

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
        from app.modules.finance.freight_sync import create_cost_expense, is_fuel_cost_tipo

        if is_fuel_cost_tipo(data.tipo):
            raise BadRequestException(
                "Registre combustível pela tela de Abastecimento para evitar duplicidade no financeiro"
            )
        cost = await self._repo.add_cost(freight_id, data.tipo, data.valor, data.descricao)
        await create_cost_expense(self._session, cost)
        await self._session.commit()
        return cost
