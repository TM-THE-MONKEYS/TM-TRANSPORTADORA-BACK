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
from app.shared.enums import FreightStatus, TruckStatus, UserRole
from app.shared.exceptions.custom import BadRequestException, ForbiddenException, NotFoundException
from app.shared.pagination import PagedResponse, PageParams
from app.shared.security.resource_access import (
    assert_freight_read_access,
    resolve_freight_list_driver_filter,
)

log = structlog.get_logger(__name__)

# Fluxo estrito: em_transporte → entregue|cancelado.
# Status legados (orcamento/confirmado/em_coleta) só como origem → em_transporte|cancelado.
# Admin pode reabrir entregue/cancelado → em_transporte.
_LEGACY_STATUSES: frozenset[FreightStatus] = frozenset(
    {FreightStatus.ORCAMENTO, FreightStatus.CONFIRMADO, FreightStatus.EM_COLETA}
)
_TERMINAL_STATUSES: frozenset[FreightStatus] = frozenset(
    {FreightStatus.ENTREGUE, FreightStatus.CANCELADO}
)
_ALLOWED_TRANSITIONS: dict[FreightStatus, frozenset[FreightStatus]] = {
    FreightStatus.ORCAMENTO: frozenset({FreightStatus.EM_TRANSPORTE, FreightStatus.CANCELADO}),
    FreightStatus.CONFIRMADO: frozenset({FreightStatus.EM_TRANSPORTE, FreightStatus.CANCELADO}),
    FreightStatus.EM_COLETA: frozenset({FreightStatus.EM_TRANSPORTE, FreightStatus.CANCELADO}),
    FreightStatus.EM_TRANSPORTE: frozenset({FreightStatus.ENTREGUE, FreightStatus.CANCELADO}),
    FreightStatus.ENTREGUE: frozenset(),
    FreightStatus.CANCELADO: frozenset(),
}

# Status que deixam o caminhão "em viagem" (espelha front IN_TRANSIT_FREIGHT_STATUSES).
_TRUCK_BUSY_STATUSES: frozenset[FreightStatus] = frozenset(
    {FreightStatus.EM_COLETA, FreightStatus.EM_TRANSPORTE}
)

# Não sobrescrever manutenção/inativo — sync só mexe em disponivel ↔ em_viagem.
_TRUCK_LOCKED_STATUSES: frozenset[TruckStatus] = frozenset(
    {TruckStatus.EM_MANUTENCAO, TruckStatus.INATIVO}
)


def _is_valid_status_transition(
    current: FreightStatus,
    target: FreightStatus,
    *,
    is_admin: bool = False,
) -> bool:
    """Valida transição. Admin pode reabrir terminal → em_transporte."""
    if current == target:
        return True
    if target in _LEGACY_STATUSES:
        return False
    if is_admin and current in _TERMINAL_STATUSES and target == FreightStatus.EM_TRANSPORTE:
        return True
    return target in _ALLOWED_TRANSITIONS.get(current, frozenset())


class FreightService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._repo = FreightRepository(session, tenant_id)

    def _check_write_access(self, user: User) -> None:
        if user.role not in (UserRole.ADMIN, UserRole.OPERADOR):
            raise ForbiddenException("Acesso negado")

    async def _sync_truck_status(self, truck_id: uuid.UUID | None) -> None:
        """Atualiza disponivel ↔ em_viagem conforme fretes ativos do caminhão.

        Fonte de verdade no backend — o front só revalida cache. Não sobrescreve
        em_manutencao / inativo.
        """
        if not truck_id:
            return
        from app.modules.trucks.models import Truck

        truck = await self._session.get(Truck, truck_id)
        if not truck or truck.tenant_id != self._tenant_id or truck.deleted_at is not None:
            return
        if truck.status in _TRUCK_LOCKED_STATUSES:
            return

        on_trip = await self._repo.has_active_freight_for_truck(truck_id)
        next_status = TruckStatus.EM_VIAGEM if on_trip else TruckStatus.DISPONIVEL
        if truck.status != next_status:
            truck.status = next_status
            await self._session.flush()
            log.info(
                "truck_status_synced",
                truck_id=str(truck_id),
                new_status=next_status.value,
                on_trip=on_trip,
            )

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
        if freight.truck_id and freight.status in _TRUCK_BUSY_STATUSES:
            await self._sync_truck_status(freight.truck_id)
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
        competencia_mes: int | None = None,
        competencia_ano: int | None = None,
        search: str | None = None,
    ) -> PagedResponse[Freight]:
        driver_id = await resolve_freight_list_driver_filter(
            self._session, requesting_user, driver_id
        )
        items, total = await self._repo.list(
            params,
            status,
            client_id,
            driver_id,
            truck_id,
            competencia_mes,
            competencia_ano,
            search,
        )
        return PagedResponse.create(items, total, params)

    async def get_summary(
        self,
        requesting_user: User,
        status: FreightStatus | None = None,
        driver_id: uuid.UUID | None = None,
        truck_id: uuid.UUID | None = None,
        competencia_mes: int | None = None,
        competencia_ano: int | None = None,
    ) -> dict[str, float | int]:
        """Resumo agregado para cards — reutilizável por Fretes / Frota / Motoristas."""
        driver_id = await resolve_freight_list_driver_filter(
            self._session, requesting_user, driver_id
        )
        return await self._repo.get_summary(
            status, driver_id, truck_id, competencia_mes, competencia_ano
        )

    async def update(self, freight_id: uuid.UUID, data: FreightUpdate, updated_by: User) -> Freight:
        self._check_write_access(updated_by)
        status_changing = data.status is not None
        freight = await self._repo.get_by_id(freight_id, for_update=status_changing)
        if not freight:
            raise NotFoundException("Frete não encontrado")
        is_admin = updated_by.role == UserRole.ADMIN
        if data.status and data.status != freight.status:
            if not _is_valid_status_transition(freight.status, data.status, is_admin=is_admin):
                raise ForbiddenException(
                    f"Transição inválida: {freight.status.value} → {data.status.value}"
                )
        old_status = freight.status
        old_truck_id = freight.truck_id
        updated_fields = data.model_dump(exclude_none=True)
        for field, value in updated_fields.items():
            setattr(freight, field, value)
        freight = await self._repo.update(freight)
        if "valor_frete" in updated_fields or "data_entrega_prevista" in updated_fields:
            from app.modules.finance.freight_sync import ensure_freight_revenue

            await ensure_freight_revenue(self._session, freight)
        if data.status and data.status != old_status:
            await self._on_status_changed(freight, old_status, data.status)
        # Sync frota: caminhão antigo (se trocou) + atual após mudança de status/truck.
        if "truck_id" in updated_fields or (data.status and data.status != old_status):
            if old_truck_id and old_truck_id != freight.truck_id:
                await self._sync_truck_status(old_truck_id)
            await self._sync_truck_status(freight.truck_id)
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
        cascade_counts = await self._hard_delete_linked_operational_records(freight_id)
        truck_id = freight.truck_id
        await self._repo.soft_delete(freight)
        await self._sync_truck_status(truck_id)
        await self._session.commit()
        log.info(
            "freight_deleted",
            freight_id=str(freight_id),
            finance_entries_removed=removed_entries,
            **cascade_counts,
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

    async def _hard_delete_linked_operational_records(self, freight_id: uuid.UUID) -> dict[str, int]:
        """Remove filhos operacionais (sem soft-delete) — frete de teste/erro não deixa órfãos.

        Ordem: notificações → combustível/pedágio → tracking → anexos/custos/paradas.
        Soft-delete do frete não dispara ON DELETE CASCADE do banco.
        """
        from sqlalchemy import delete

        from app.modules.freights.models import FreightAttachment, FreightCost, FreightStop
        from app.modules.fuel.models import FuelRefill
        from app.modules.notifications.models import FreightNotification, NotificationRead
        from app.modules.tolls.models import TollCharge
        from app.modules.tracking.models import TrackingUpdate

        notification_ids = select(FreightNotification.id).where(
            FreightNotification.freight_id == freight_id,
            FreightNotification.tenant_id == self._tenant_id,
        )
        reads = await self._session.execute(
            delete(NotificationRead).where(NotificationRead.notification_id.in_(notification_ids))
        )
        notifications = await self._session.execute(
            delete(FreightNotification).where(
                FreightNotification.freight_id == freight_id,
                FreightNotification.tenant_id == self._tenant_id,
            )
        )
        fuel = await self._session.execute(
            delete(FuelRefill).where(
                FuelRefill.freight_id == freight_id,
                FuelRefill.tenant_id == self._tenant_id,
            )
        )
        tolls = await self._session.execute(
            delete(TollCharge).where(
                TollCharge.freight_id == freight_id,
                TollCharge.tenant_id == self._tenant_id,
            )
        )
        tracking = await self._session.execute(
            delete(TrackingUpdate).where(
                TrackingUpdate.freight_id == freight_id,
                TrackingUpdate.tenant_id == self._tenant_id,
            )
        )
        attachments = await self._session.execute(
            delete(FreightAttachment).where(
                FreightAttachment.freight_id == freight_id,
                FreightAttachment.tenant_id == self._tenant_id,
            )
        )
        costs = await self._session.execute(
            delete(FreightCost).where(
                FreightCost.freight_id == freight_id,
                FreightCost.tenant_id == self._tenant_id,
            )
        )
        stops = await self._session.execute(
            delete(FreightStop).where(
                FreightStop.freight_id == freight_id,
                FreightStop.tenant_id == self._tenant_id,
            )
        )
        await self._session.flush()
        return {
            "notification_reads_removed": reads.rowcount or 0,
            "notifications_removed": notifications.rowcount or 0,
            "fuel_refills_removed": fuel.rowcount or 0,
            "toll_charges_removed": tolls.rowcount or 0,
            "tracking_updates_removed": tracking.rowcount or 0,
            "attachments_removed": attachments.rowcount or 0,
            "costs_removed": costs.rowcount or 0,
            "stops_removed": stops.rowcount or 0,
        }

    async def advance_status(self, freight_id: uuid.UUID, requesting_user: User) -> Freight:
        self._check_write_access(requesting_user)
        freight = await self._repo.get_by_id(freight_id, for_update=True)
        if not freight:
            raise NotFoundException("Frete não encontrado")
        if freight.status in _LEGACY_STATUSES:
            next_status = FreightStatus.EM_TRANSPORTE
        elif freight.status == FreightStatus.EM_TRANSPORTE:
            next_status = FreightStatus.ENTREGUE
        else:
            raise ForbiddenException("Frete já está no status final")
        return await self._apply_status_change(freight, next_status, commit=True)

    async def update_status(
        self, freight_id: uuid.UUID, new_status: FreightStatus, requesting_user: User
    ) -> Freight:
        self._check_write_access(requesting_user)
        freight = await self._repo.get_by_id(freight_id, for_update=True)
        if not freight:
            raise NotFoundException("Frete não encontrado")
        is_admin = requesting_user.role == UserRole.ADMIN
        if new_status != freight.status and not _is_valid_status_transition(
            freight.status, new_status, is_admin=is_admin
        ):
            raise ForbiddenException(
                f"Transição inválida: {freight.status.value} → {new_status.value}"
            )
        if new_status == freight.status:
            freight = await self._repo.get_by_id(freight_id, with_relations=True)
            assert freight is not None
            return freight
        return await self._apply_status_change(freight, new_status, commit=True)

    async def mark_delivered_from_tracking(
        self, freight_id: uuid.UUID, *, commit: bool = False
    ) -> Freight | None:
        """Avança frete para entregue quando tracking registra entrega.

        Não exige papel de escrita no frete — quem já pode lançar tracking
        (admin/operador/motorista) dispara a conclusão. Idempotente se já entregue.
        Não reabre cancelado.
        """
        freight = await self._repo.get_by_id(freight_id, for_update=True)
        if not freight:
            raise NotFoundException("Frete não encontrado")
        if freight.status == FreightStatus.ENTREGUE:
            return freight
        if freight.status == FreightStatus.CANCELADO:
            raise BadRequestException(
                "Não é possível marcar entrega em frete cancelado"
            )
        if not _is_valid_status_transition(
            freight.status, FreightStatus.ENTREGUE, is_admin=False
        ):
            # Legado → primeiro normaliza para em_transporte, depois entrega no mesmo flush.
            if freight.status in _LEGACY_STATUSES:
                old = freight.status
                freight.status = FreightStatus.EM_TRANSPORTE
                freight = await self._repo.update(freight)
                await self._on_status_changed(freight, old, FreightStatus.EM_TRANSPORTE)
            else:
                raise ForbiddenException(
                    f"Transição inválida: {freight.status.value} → entregue"
                )
        return await self._apply_status_change(
            freight, FreightStatus.ENTREGUE, commit=commit
        )

    async def _apply_status_change(
        self,
        freight: Freight,
        new_status: FreightStatus,
        *,
        commit: bool,
    ) -> Freight:
        freight_id = freight.id
        old_status = freight.status
        freight.status = new_status
        freight = await self._repo.update(freight)
        if new_status != old_status:
            await self._on_status_changed(freight, old_status, new_status)
            await self._sync_truck_status(freight.truck_id)
        if commit:
            await self._session.commit()
            freight = await self._repo.get_by_id(freight_id, with_relations=True)
            assert freight is not None
        log.info(
            "freight_status_updated",
            freight_id=str(freight_id),
            old_status=old_status.value,
            new_status=new_status.value,
        )
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
