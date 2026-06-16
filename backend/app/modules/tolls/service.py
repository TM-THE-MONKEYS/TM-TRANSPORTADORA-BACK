"""Toll charge (pedágio) service."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.drivers.models import Driver
from app.modules.freights.models import Freight, FreightCost
from app.modules.freights.repository import FreightRepository
from app.modules.tolls.models import TollCharge
from app.modules.tolls.repository import TollRepository
from app.modules.tolls.schemas import (
    ActiveFreightContext,
    EligibleFreightItem,
    TollChargeCreate,
    TollChargeCreatedResponse,
    TollChargeRead,
    TollFreightSummary,
)
from app.modules.notifications.service import NotificationService, freight_code
from app.modules.trucks.models import Truck
from app.modules.users.models import User
from app.shared.enums import ACTIVE_FREIGHT_STATUSES, UserRole
from app.shared.exceptions.custom import BadRequestException, ForbiddenException, NotFoundException
from app.shared.pagination import PagedResponse, PageParams
from app.shared.security.resource_access import (
    assert_freight_read_access,
    get_driver_id_for_user,
)

log = structlog.get_logger(__name__)

_WRITE_ROLES = frozenset({UserRole.ADMIN, UserRole.OPERADOR, UserRole.MOTORISTA})
_READ_ROLES = frozenset(
    {UserRole.ADMIN, UserRole.OPERADOR, UserRole.MOTORISTA, UserRole.FINANCEIRO}
)


class TollService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._repo = TollRepository(session, tenant_id)
        self._freight_repo = FreightRepository(session, tenant_id)

    def _check_write_access(self, user: User) -> None:
        if user.role not in _WRITE_ROLES:
            raise ForbiddenException("Acesso negado")

    async def _resolve_driver_id(
        self, freight: Freight, payload_driver_id: uuid.UUID | None, user: User
    ) -> uuid.UUID:
        if not freight.driver_id:
            raise BadRequestException(
                "Frete sem motorista vinculado. Atribua um motorista antes de registrar pedágio."
            )

        if payload_driver_id and payload_driver_id != freight.driver_id:
            raise BadRequestException(
                "O pedágio deve ser registrado pelo motorista vinculado ao frete"
            )

        if user.role == UserRole.MOTORISTA:
            my_driver_id = await get_driver_id_for_user(self._session, user)
            if not my_driver_id or freight.driver_id != my_driver_id:
                raise ForbiddenException(
                    "Somente o motorista do frete pode registrar pedágio"
                )

        return freight.driver_id

    async def _check_freight_active(self, freight: Freight) -> None:
        if freight.status not in ACTIVE_FREIGHT_STATUSES:
            raise BadRequestException(
                "Pedágio só pode ser registrado em frete confirmado, em coleta ou em transporte"
            )

    async def _enrich_read(self, charge: TollCharge) -> TollChargeRead:
        driver_name: str | None = None
        if charge.driver_id:
            driver = await self._session.get(Driver, charge.driver_id)
            driver_name = driver.nome if driver else None

        return TollChargeRead(
            id=charge.id,
            freight_id=charge.freight_id,
            driver_id=charge.driver_id,
            registrado_por_user_id=charge.registrado_por_user_id,
            freight_cost_id=charge.freight_cost_id,
            valor=charge.valor,
            quantidade=charge.quantidade,
            praca=charge.praca,
            rodovia=charge.rodovia,
            cidade=charge.cidade,
            estado=charge.estado,
            observacoes=charge.observacoes,
            data_pedagio=charge.data_pedagio,
            created_at=charge.created_at,
            freight_code=freight_code(charge.freight_id),
            driver_name=driver_name,
        )

    async def create(
        self, data: TollChargeCreate, author: User
    ) -> TollChargeCreatedResponse:
        self._check_write_access(author)
        freight = await self._freight_repo.get_by_id(data.freight_id)
        if not freight:
            raise NotFoundException("Frete não encontrado")

        await assert_freight_read_access(self._session, freight, author)
        await self._check_freight_active(freight)
        driver_id = await self._resolve_driver_id(freight, data.driver_id, author)

        valor = float(data.valor)
        quantidade = int(data.quantidade)

        cost_desc = self._build_cost_description(valor, quantidade, data.praca, data.rodovia, data.cidade)
        cost = FreightCost(
            freight_id=freight.id,
            tipo="PEDAGIO",
            valor=valor,
            descricao=cost_desc,
            tenant_id=self._tenant_id,
        )
        self._session.add(cost)
        await self._session.flush()

        charge = TollCharge(
            freight_id=freight.id,
            driver_id=driver_id,
            registrado_por_user_id=author.id,
            freight_cost_id=cost.id,
            valor=valor,
            quantidade=quantidade,
            praca=data.praca,
            rodovia=data.rodovia,
            cidade=data.cidade,
            estado=data.estado,
            observacoes=data.observacoes,
            data_pedagio=data.data_pedagio or datetime.now(timezone.utc),
            tenant_id=self._tenant_id,
        )
        charge = await self._repo.create(charge)

        from app.modules.finance.freight_sync import create_toll_expense

        await create_toll_expense(self._session, charge, cost_desc)

        notification_service = NotificationService(self._session, self._tenant_id)
        notification = await notification_service.create_for_toll_charge(charge, author)

        await self._session.commit()
        log.info(
            "toll_charge_created",
            charge_id=str(charge.id),
            freight_id=str(freight.id),
            driver_id=str(driver_id),
            valor=valor,
            quantidade=quantidade,
        )
        base = await self._enrich_read(charge)
        return TollChargeCreatedResponse(
            **base.model_dump(),
            notification_id=notification.id,
        )

    @staticmethod
    def _build_cost_description(
        valor: float,
        quantidade: int,
        praca: str | None,
        rodovia: str | None,
        cidade: str | None,
    ) -> str:
        parts = [f"PEDÁGIO {quantidade}x — R$ {valor:.2f}"]
        if praca:
            parts.append(praca.upper())
        if rodovia:
            parts.append(rodovia.upper())
        if cidade:
            parts.append(cidade.upper())
        return " — ".join(parts)

    async def get_by_id(self, charge_id: uuid.UUID, user: User) -> TollChargeRead:
        charge = await self._repo.get_by_id(charge_id)
        if not charge:
            raise NotFoundException("Pedágio não encontrado")
        freight = await self._freight_repo.get_by_id(charge.freight_id)
        if freight:
            await assert_freight_read_access(self._session, freight, user)
        return await self._enrich_read(charge)

    async def list_all(
        self,
        params: PageParams,
        user: User,
    ) -> PagedResponse[TollChargeRead]:
        if user.role not in _READ_ROLES:
            raise ForbiddenException("Acesso negado")

        driver_filter: uuid.UUID | None = None
        if user.role == UserRole.MOTORISTA:
            driver_filter = await get_driver_id_for_user(self._session, user)
            if not driver_filter:
                return PagedResponse.create([], 0, params)

        items, total = await self._repo.list_all(
            driver_id=driver_filter,
            limit=params.size,
            offset=params.offset,
        )
        reads = [await self._enrich_read(c) for c in items]
        return PagedResponse.create(reads, total, params)

    async def list_by_freight(
        self,
        freight_id: uuid.UUID,
        params: PageParams,
        user: User,
    ) -> PagedResponse[TollChargeRead]:
        freight = await self._freight_repo.get_by_id(freight_id)
        if not freight:
            raise NotFoundException("Frete não encontrado")
        await assert_freight_read_access(self._session, freight, user)

        items, total = await self._repo.list_by_freight(
            freight_id, limit=params.size, offset=params.offset
        )
        reads = [await self._enrich_read(c) for c in items]
        return PagedResponse.create(reads, total, params)

    async def get_freight_summary(
        self, freight_id: uuid.UUID, user: User
    ) -> TollFreightSummary:
        freight = await self._freight_repo.get_by_id(freight_id)
        if not freight:
            raise NotFoundException("Frete não encontrado")
        await assert_freight_read_access(self._session, freight, user)

        total_valor, total_quantidade, count = await self._repo.summarize_freight(freight_id)
        driver_name: str | None = None
        if freight.driver_id:
            driver = await self._session.get(Driver, freight.driver_id)
            driver_name = driver.nome if driver else None

        return TollFreightSummary(
            freight_id=freight_id,
            freight_code=freight_code(freight_id),
            status=freight.status.value,
            driver_id=freight.driver_id,
            driver_name=driver_name,
            total_valor=total_valor,
            total_quantidade=total_quantidade,
            charges_count=count,
        )

    async def _build_freight_context(self, freight: Freight) -> ActiveFreightContext:
        if not freight.driver_id:
            raise NotFoundException("Frete sem motorista vinculado")

        driver = await self._session.get(Driver, freight.driver_id)
        if not driver:
            raise NotFoundException("Motorista não encontrado")

        truck_plate: str | None = None
        if freight.truck_id:
            truck = await self._session.get(Truck, freight.truck_id)
            truck_plate = truck.placa if truck else None

        origem = freight.origem or {}
        destino = freight.destino or {}
        return ActiveFreightContext(
            freight_id=freight.id,
            freight_code=freight_code(freight.id),
            status=freight.status.value,
            driver_id=driver.id,
            driver_name=driver.nome,
            truck_id=freight.truck_id,
            truck_plate=truck_plate,
            origin_city=origem.get("cidade", ""),
            origin_state=origem.get("estado", ""),
            destination_city=destino.get("cidade", ""),
            destination_state=destino.get("estado", ""),
        )

    async def list_eligible_freights(self, user: User) -> list[EligibleFreightItem]:
        if user.role not in _READ_ROLES:
            raise ForbiddenException("Acesso negado")

        driver_filter: uuid.UUID | None = None
        if user.role == UserRole.MOTORISTA:
            driver_filter = await get_driver_id_for_user(self._session, user)
            if not driver_filter:
                return []

        fretes, _ = await self._repo.list_eligible_freights(driver_id=driver_filter)
        return [EligibleFreightItem(**(await self._build_freight_context(f)).model_dump()) for f in fretes]

    async def get_active_freight_context(self, user: User) -> ActiveFreightContext:
        if user.role != UserRole.MOTORISTA:
            raise ForbiddenException("Disponível apenas para motoristas")

        freight_id = await self._repo.get_active_freight_for_driver_user(user.id)
        if not freight_id:
            raise NotFoundException("Nenhum frete em andamento encontrado para este motorista")

        freight = await self._freight_repo.get_by_id(freight_id)
        if not freight:
            raise NotFoundException("Frete em andamento inválido")

        return await self._build_freight_context(freight)
