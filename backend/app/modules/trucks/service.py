"""Truck service."""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.status_history.service import StatusHistoryService
from app.modules.trucks.models import Truck
from app.modules.trucks.repository import TruckRepository
from app.modules.trucks.consumption import build_truck_consumption
from app.modules.trucks.schemas import (
    ConsumptionSegmentRead,
    TruckConsumptionRead,
    TruckCreate,
    TruckUpdate,
)
from app.modules.users.models import User
from app.shared.enums import StatusChangeSource, StatusEntityType, TruckStatus, UserRole
from app.shared.exceptions.custom import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.shared.pagination import PagedResponse, PageParams
from app.shared.security.resource_access import assert_catalog_read_access

log = structlog.get_logger(__name__)


class TruckService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._repo = TruckRepository(session, tenant_id)

    def _check_write_access(self, user: User) -> None:
        if user.role not in (UserRole.ADMIN, UserRole.OPERADOR):
            raise ForbiddenException("Acesso negado")

    async def create(self, data: TruckCreate, created_by: User) -> Truck:
        self._check_write_access(created_by)
        if await self._repo.get_by_placa(data.placa):
            raise ConflictException("Placa já cadastrada")
        truck = Truck(**data.model_dump())
        truck = await self._repo.create(truck)
        await self._session.commit()
        log.info("truck_created", truck_id=str(truck.id), placa=truck.placa)
        return truck

    async def get_by_id(self, truck_id: uuid.UUID, requesting_user: User) -> Truck:
        assert_catalog_read_access(requesting_user)
        truck = await self._repo.get_by_id(truck_id)
        if not truck:
            raise NotFoundException("Caminhão não encontrado")
        return truck

    async def list(
        self,
        params: PageParams,
        requesting_user: User,
        status: TruckStatus | None = None,
        search: str | None = None,
    ) -> PagedResponse[Truck]:
        assert_catalog_read_access(requesting_user)
        items, total = await self._repo.list(params, status, search)
        return PagedResponse.create(items, total, params)

    async def update(self, truck_id: uuid.UUID, data: TruckUpdate, updated_by: User) -> Truck:
        self._check_write_access(updated_by)
        truck = await self.get_by_id(truck_id, updated_by)
        old_status = truck.status
        fields = data.model_dump(exclude_none=True)
        for field, value in fields.items():
            setattr(truck, field, value)
        if "status" in fields and truck.status != old_status:
            await StatusHistoryService(self._session, self._tenant_id).record(
                entity_type=StatusEntityType.TRUCK,
                entity_id=truck.id,
                from_status=old_status.value,
                to_status=truck.status.value,
                source=StatusChangeSource.API,
                user_id=updated_by.id,
            )
        truck = await self._repo.update(truck)
        await self._session.commit()
        return truck

    async def delete(self, truck_id: uuid.UUID, deleted_by: User) -> None:
        self._check_write_access(deleted_by)
        truck = await self.get_by_id(truck_id, deleted_by)
        if truck.status == TruckStatus.EM_VIAGEM:
            raise ForbiddenException("Não é possível remover caminhão em viagem")
        await self._repo.soft_delete(truck)
        await self._session.commit()
        log.info("truck_deleted", truck_id=str(truck_id))

    async def get_consumption(
        self, truck_id: uuid.UUID, requesting_user: User
    ) -> TruckConsumptionRead:
        truck = await self.get_by_id(truck_id, requesting_user)
        report = await build_truck_consumption(
            self._session, self._tenant_id, truck
        )
        return TruckConsumptionRead(
            truck_id=report.truck_id,
            plate=report.placa,
            consumo_cadastrado_km_l=report.consumo_cadastrado_km_l,
            consumo_real_km_l=report.consumo_real_km_l,
            desvio_pct=report.desvio_pct,
            desvio_relevante=report.desvio_relevante,
            km_rodado_total=report.km_rodado_total,
            custo_combustivel=report.custo_combustivel,
            custo_pedagio=report.custo_pedagio,
            custo_por_km=report.custo_por_km,
            segmentos=[
                ConsumptionSegmentRead(
                    from_refill_id=s.from_refill_id,
                    to_refill_id=s.to_refill_id,
                    km_start=s.km_start,
                    km_end=s.km_end,
                    km_rodado=s.km_rodado,
                    litros=s.litros,
                    km_l=s.km_l,
                )
                for s in report.segmentos
            ],
        )

    async def update_km(self, truck_id: uuid.UUID, km: float, updated_by: User) -> Truck:
        self._check_write_access(updated_by)
        truck = await self.get_by_id(truck_id, updated_by)
        if km < truck.km_atual:
            raise ValueError("KM não pode ser menor que o atual")
        truck.km_atual = km
        truck = await self._repo.update(truck)
        await self._session.commit()
        return truck
