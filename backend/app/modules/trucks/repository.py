"""Truck repository."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.trucks.models import Truck
from app.shared.base_repository import TenantBaseRepository
from app.shared.enums import TruckStatus
from app.shared.filters.competencia import matching_freight_exists
from app.shared.pagination import PageParams

_OPERATIONAL_STATUSES = (TruckStatus.DISPONIVEL, TruckStatus.EM_VIAGEM)


class TruckRepository(TenantBaseRepository[Truck]):
    model = Truck

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        super().__init__(session, tenant_id)

    async def get_by_placa(self, placa: str) -> Truck | None:
        result = await self._session.execute(
            self._base_query().where(Truck.placa == placa.upper())
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        params: PageParams,
        status: TruckStatus | None = None,
        search: str | None = None,
        competencia_mes: int | None = None,
        competencia_ano: int | None = None,
        driver_id: uuid.UUID | None = None,
    ) -> tuple[list[Truck], int]:
        query = self._base_query()
        if status:
            query = query.where(Truck.status == status)
        if search:
            term = f"%{search}%"
            query = query.where(
                Truck.placa.ilike(term)
                | Truck.modelo.ilike(term)
                | Truck.marca.ilike(term)
            )
        if competencia_mes is not None or driver_id is not None:
            query = query.where(
                matching_freight_exists(
                    tenant_id=self._tenant_id,
                    truck_id_column=Truck.id,
                    driver_id=driver_id,
                    competencia_mes=competencia_mes,
                    competencia_ano=competencia_ano,
                )
            )
        total = await self._count(query)
        result = await self._session.execute(
            query.order_by(Truck.placa).offset(params.offset).limit(params.limit)
        )
        return list(result.scalars().all()), total

    async def count_by_status(self) -> dict[str, int]:
        result = await self._session.execute(
            select(Truck.status, func.count(Truck.id))
            .where(Truck.deleted_at.is_(None), Truck.tenant_id == self._tenant_id)
            .group_by(Truck.status)
        )
        return {row[0].value: row[1] for row in result.all()}

    async def count_operational(
        self,
        *,
        truck_id: uuid.UUID | None = None,
        driver_id: uuid.UUID | None = None,
        client_id: uuid.UUID | None = None,
        competencia_mes: int | None = None,
        competencia_ano: int | None = None,
        period_from: date | None = None,
        period_to: date | None = None,
    ) -> int:
        """Caminhões disponivel+em_viagem, opcionalmente restritos por frete."""
        query = select(func.count(Truck.id)).where(
            Truck.deleted_at.is_(None),
            Truck.tenant_id == self._tenant_id,
            Truck.status.in_(_OPERATIONAL_STATUSES),
        )
        if truck_id is not None:
            query = query.where(Truck.id == truck_id)
        elif (
            driver_id is not None
            or client_id is not None
            or competencia_mes is not None
            or period_from is not None
            or period_to is not None
        ):
            query = query.where(
                matching_freight_exists(
                    tenant_id=self._tenant_id,
                    truck_id_column=Truck.id,
                    driver_id=driver_id,
                    client_id=client_id,
                    competencia_mes=competencia_mes,
                    competencia_ano=competencia_ano,
                    period_from=period_from,
                    period_to=period_to,
                )
            )
        result = await self._session.execute(query)
        return int(result.scalar_one() or 0)
