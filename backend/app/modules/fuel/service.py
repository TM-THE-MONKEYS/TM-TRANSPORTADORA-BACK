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
    FuelFreightSummary,
    FuelRefillCreate,
    FuelRefillCreatedResponse,
    FuelRefillRead,
)
from app.modules.notifications.service import NotificationService, freight_code
from app.modules.trucks.models import Truck
from app.modules.users.models import User
from app.shared.enums import ACTIVE_FREIGHT_STATUSES, UserRole
from app.shared.exceptions.custom import BadRequestException, ForbiddenException, NotFoundException
from app.shared.pagination import PagedResponse, PageParams

log = structlog.get_logger(__name__)

_WRITE_ROLES = frozenset({UserRole.ADMIN, UserRole.OPERADOR, UserRole.MOTORISTA})


class FuelService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = FuelRepository(session)
        self._freight_repo = FreightRepository(session)

    def _check_write_access(self, user: User) -> None:
        if user.role not in _WRITE_ROLES:
            raise ForbiddenException("Acesso negado")

    async def _resolve_driver_id(
        self, freight: Freight, payload_driver_id: uuid.UUID | None, user: User
    ) -> uuid.UUID:
        driver_id = payload_driver_id or freight.driver_id
        if not driver_id:
            raise BadRequestException(
                "Frete sem motorista vinculado. Atribua um motorista antes do abastecimento."
            )

        if user.role == UserRole.MOTORISTA:
            result = await self._session.execute(
                select(Driver.id).where(Driver.user_id == user.id)
            )
            my_driver_id = result.scalar_one_or_none()
            if not my_driver_id or my_driver_id != driver_id:
                raise ForbiddenException("Motorista só pode registrar abastecimento do próprio frete")
            if freight.driver_id and freight.driver_id != my_driver_id:
                raise ForbiddenException("Este frete não está atribuído a você")

        if freight.driver_id and driver_id != freight.driver_id:
            raise BadRequestException("Motorista informado não corresponde ao frete")

        return driver_id

    async def _check_freight_active_for_refill(self, freight: Freight) -> None:
        if freight.status not in ACTIVE_FREIGHT_STATUSES:
            raise BadRequestException(
                "Abastecimento só pode ser registrado em frete confirmado, em coleta ou em transporte"
            )

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
        )
        refill = await self._repo.create(refill)

        notification_service = NotificationService(self._session)
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
        if user.role == UserRole.MOTORISTA and freight.driver_id:
            result = await self._session.execute(
                select(Driver.user_id).where(Driver.id == freight.driver_id)
            )
            driver_user_id = result.scalar_one_or_none()
            if driver_user_id != user.id:
                raise ForbiddenException("Acesso negado a este frete")

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

    async def get_active_freight_context(self, user: User) -> ActiveFreightContext:
        if user.role != UserRole.MOTORISTA:
            raise ForbiddenException("Disponível apenas para motoristas")

        freight_id = await self._repo.get_active_freight_for_driver_user(user.id)
        if not freight_id:
            raise NotFoundException("Nenhum frete em andamento encontrado para este motorista")

        freight = await self._freight_repo.get_by_id(freight_id)
        if not freight or not freight.driver_id:
            raise NotFoundException("Frete em andamento inválido")

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
