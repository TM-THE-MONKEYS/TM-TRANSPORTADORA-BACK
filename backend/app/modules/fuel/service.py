"""Fuel refill service."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.drivers.models import Driver
from app.modules.freights.models import Freight, FreightCost
from app.modules.freights.repository import FreightRepository
from app.modules.fuel.models import FuelRefill
from app.modules.fuel.repository import FuelRepository
from app.modules.fuel.schemas import (
    ActiveFreightContext,
    EligibleFreightItem,
    FuelFreightSummary,
    FuelRefillCreate,
    FuelRefillCreatedResponse,
    FuelRefillRead,
)
from app.modules.notifications.service import NotificationService, freight_code
from app.modules.trucks.models import Truck
from app.modules.trucks.repository import TruckRepository
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
_READ_ELIGIBLE_ROLES = frozenset(
    {UserRole.ADMIN, UserRole.OPERADOR, UserRole.MOTORISTA, UserRole.FINANCEIRO}
)


class FuelService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._repo = FuelRepository(session, tenant_id)
        self._freight_repo = FreightRepository(session, tenant_id)

    def _check_write_access(self, user: User) -> None:
        if user.role not in _WRITE_ROLES:
            raise ForbiddenException("Acesso negado")

    async def _resolve_driver_id(
        self, freight: Freight, payload_driver_id: uuid.UUID | None, user: User
    ) -> uuid.UUID:
        if not freight.driver_id:
            raise BadRequestException(
                "Frete sem motorista vinculado. Atribua um motorista antes do abastecimento."
            )

        if payload_driver_id and payload_driver_id != freight.driver_id:
            raise BadRequestException(
                "O abastecimento deve ser registrado pelo motorista vinculado ao frete"
            )

        if user.role == UserRole.MOTORISTA:
            my_driver_id = await get_driver_id_for_user(self._session, user)
            if not my_driver_id or freight.driver_id != my_driver_id:
                raise ForbiddenException(
                    "Somente o motorista do frete pode registrar abastecimento"
                )

        return freight.driver_id

    async def _check_freight_active_for_refill(self, freight: Freight) -> None:
        if freight.status not in ACTIVE_FREIGHT_STATUSES:
            raise BadRequestException(
                "Abastecimento só pode ser registrado em frete confirmado, em coleta ou em transporte"
            )

    async def _sync_truck_km(self, truck_id: uuid.UUID, km: float) -> None:
        """Atualiza km_atual do caminhão na frota (registro pelo motorista no abastecimento)."""
        truck = await self._session.get(Truck, truck_id)
        if not truck or truck.deleted_at is not None:
            raise BadRequestException("Caminhão vinculado ao frete não encontrado na frota")
        if km <= 0:
            raise BadRequestException("Informe a quilometragem atual do veículo")
        current = float(truck.km_atual or 0)
        if km < current:
            raise BadRequestException(
                f"A quilometragem ({km:,.0f} km) não pode ser menor que a da frota ({current:,.0f} km)"
            )
        truck.km_atual = km

    async def _enrich_read(self, refill: FuelRefill) -> FuelRefillRead:
        driver_name: str | None = None
        truck_plate: str | None = None
        if refill.driver_id:
            driver = await self._session.get(Driver, refill.driver_id)
            driver_name = driver.nome if driver else None
        if refill.truck_id:
            truck = await self._session.get(Truck, refill.truck_id)
            truck_plate = truck.placa if truck else None

        valor_litro = refill.valor_litro
        if valor_litro is None and refill.litros > 0:
            valor_litro = round(refill.valor_total / refill.litros, 4)

        return FuelRefillRead(
            id=refill.id,
            freight_id=refill.freight_id,
            driver_id=refill.driver_id,
            truck_id=refill.truck_id,
            registrado_por_user_id=refill.registrado_por_user_id,
            freight_cost_id=refill.freight_cost_id,
            litros=refill.litros,
            valor_total=refill.valor_total,
            valor_litro=valor_litro,
            km_atual=refill.km_atual,
            posto=refill.posto,
            cidade=refill.cidade,
            estado=refill.estado,
            observacoes=refill.observacoes,
            data_abastecimento=refill.data_abastecimento,
            created_at=refill.created_at,
            freight_code=freight_code(refill.freight_id),
            driver_name=driver_name,
            truck_plate=truck_plate,
        )

    async def create(
        self, data: FuelRefillCreate, author: User
    ) -> FuelRefillCreatedResponse:
        self._check_write_access(author)
        freight = await self._freight_repo.get_by_id(data.freight_id)
        if not freight:
            raise NotFoundException("Frete não encontrado")

        await assert_freight_read_access(self._session, freight, author)
        await self._check_freight_active_for_refill(freight)
        driver_id = await self._resolve_driver_id(freight, data.driver_id, author)
        truck_id = data.truck_id or freight.truck_id

        litros = float(data.litros)
        valor_total = float(data.valor_total)
        valor_litro = data.valor_litro
        if valor_litro is None and litros > 0:
            valor_litro = round(valor_total / litros, 4)

        cost_desc = self._build_cost_description(litros, valor_total, data.posto, data.cidade)
        cost = FreightCost(
            freight_id=freight.id,
            tipo="COMBUSTIVEL",
            valor=valor_total,
            descricao=cost_desc,
            tenant_id=self._tenant_id,
        )
        self._session.add(cost)
        await self._session.flush()

        refill = FuelRefill(
            freight_id=freight.id,
            driver_id=driver_id,
            truck_id=truck_id,
            registrado_por_user_id=author.id,
            freight_cost_id=cost.id,
            litros=litros,
            valor_total=valor_total,
            valor_litro=valor_litro,
            km_atual=data.km_atual,
            posto=data.posto,
            cidade=data.cidade,
            estado=data.estado,
            observacoes=data.observacoes,
            data_abastecimento=data.data_abastecimento or datetime.now(timezone.utc),
            tenant_id=self._tenant_id,
        )
        refill = await self._repo.create(refill)

        if truck_id:
            if data.km_atual is None:
                raise BadRequestException(
                    "Informe a quilometragem atual do caminhão para atualizar a frota"
                )
            await self._sync_truck_km(truck_id, float(data.km_atual))
        elif data.km_atual is not None:
            raise BadRequestException("Frete sem caminhão vinculado — quilometragem não aplicada")

        from app.modules.finance.freight_sync import create_fuel_expense

        await create_fuel_expense(self._session, refill, cost_desc)

        notification_service = NotificationService(self._session, self._tenant_id)
        notification = await notification_service.create_for_fuel_refill(refill, author)

        await self._session.commit()
        log.info(
            "fuel_refill_created",
            refill_id=str(refill.id),
            freight_id=str(freight.id),
            driver_id=str(driver_id),
            litros=litros,
            valor_total=valor_total,
        )
        base = await self._enrich_read(refill)
        return FuelRefillCreatedResponse(
            **base.model_dump(),
            notification_id=notification.id,
        )

    @staticmethod
    def _build_cost_description(
        litros: float,
        valor_total: float,
        posto: str | None,
        cidade: str | None,
    ) -> str:
        parts = [f"ABASTECIMENTO {litros:.2f}L — R$ {valor_total:.2f}"]
        if posto:
            parts.append(posto.upper())
        if cidade:
            parts.append(cidade.upper())
        return " — ".join(parts)

    async def get_by_id(self, refill_id: uuid.UUID, user: User) -> FuelRefillRead:
        refill = await self._repo.get_by_id(refill_id)
        if not refill:
            raise NotFoundException("Abastecimento não encontrado")
        freight = await self._freight_repo.get_by_id(refill.freight_id)
        if freight:
            await self._check_read_access(freight, user)
        return await self._enrich_read(refill)

    async def _check_read_access(self, freight: Freight, user: User) -> None:
        await assert_freight_read_access(self._session, freight, user)

    async def list_all(
        self,
        params: PageParams,
        user: User,
    ) -> PagedResponse[FuelRefillRead]:
        if user.role not in _READ_ELIGIBLE_ROLES:
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
        reads = [await self._enrich_read(r) for r in items]
        return PagedResponse.create(reads, total, params)

    async def list_by_freight(
        self,
        freight_id: uuid.UUID,
        params: PageParams,
        user: User,
    ) -> PagedResponse[FuelRefillRead]:
        freight = await self._freight_repo.get_by_id(freight_id)
        if not freight:
            raise NotFoundException("Frete não encontrado")
        await self._check_read_access(freight, user)

        items, total = await self._repo.list_by_freight(
            freight_id, limit=params.size, offset=params.offset
        )
        reads = [await self._enrich_read(r) for r in items]
        return PagedResponse.create(reads, total, params)

    async def get_freight_summary(
        self, freight_id: uuid.UUID, user: User
    ) -> FuelFreightSummary:
        freight = await self._freight_repo.get_by_id(freight_id)
        if not freight:
            raise NotFoundException("Frete não encontrado")
        await self._check_read_access(freight, user)

        total_litros, total_valor, count = await self._repo.summarize_freight(freight_id)
        driver_name: str | None = None
        truck_plate: str | None = None
        if freight.driver_id:
            driver = await self._session.get(Driver, freight.driver_id)
            driver_name = driver.nome if driver else None
        if freight.truck_id:
            truck = await self._session.get(Truck, freight.truck_id)
            truck_plate = truck.placa if truck else None

        return FuelFreightSummary(
            freight_id=freight_id,
            freight_code=freight_code(freight_id),
            status=freight.status.value,
            driver_id=freight.driver_id,
            driver_name=driver_name,
            truck_id=freight.truck_id,
            truck_plate=truck_plate,
            total_litros=total_litros,
            total_valor=total_valor,
            refills_count=count,
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
        if user.role not in _READ_ELIGIBLE_ROLES:
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
