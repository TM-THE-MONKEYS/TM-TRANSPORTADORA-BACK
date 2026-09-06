"""Driver repository."""
from __future__ import annotations

import uuid
from datetime import date

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.drivers.models import Driver
from app.shared.base_repository import TenantBaseRepository
from app.shared.enums import DriverStatus
from app.shared.filters.competencia import matching_freight_exists
from app.shared.pagination import PageParams

log = structlog.get_logger(__name__)


class DriverRepository(TenantBaseRepository[Driver]):
    model = Driver

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        super().__init__(session, tenant_id)

    async def get_by_cpf(self, cpf: str) -> Driver | None:
        result = await self._session.execute(
            self._base_query().where(Driver.cpf == cpf)
        )
        return result.scalar_one_or_none()

    async def get_by_cnh(self, cnh: str) -> Driver | None:
        result = await self._session.execute(
            self._base_query().where(Driver.cnh == cnh)
        )
        return result.scalar_one_or_none()

    async def exists_by_cpf(self, cpf: str) -> bool:
        """Global check — CPF unique constraint is not scoped by tenant."""
        result = await self._session.execute(
            select(Driver.id).where(Driver.cpf == cpf)
        )
        return result.scalar_one_or_none() is not None

    async def exists_by_cnh(self, cnh: str) -> bool:
        """Global check — CNH unique constraint is not scoped by tenant."""
        result = await self._session.execute(
            select(Driver.id).where(Driver.cnh == cnh)
        )
        return result.scalar_one_or_none() is not None

    async def list(
        self,
        params: PageParams,
        status: DriverStatus | None = None,
        search: str | None = None,
        competencia_mes: int | None = None,
        competencia_ano: int | None = None,
        truck_id: uuid.UUID | None = None,
    ) -> tuple[list[Driver], int]:
        query = self._base_query()
        if status:
            query = query.where(Driver.status == status)
        if search:
            term = f"%{search}%"
            query = query.where(
                Driver.nome.ilike(term) | Driver.cpf.ilike(term) | Driver.cnh.ilike(term)
            )
        if competencia_mes is not None or truck_id is not None:
            query = query.where(
                matching_freight_exists(
                    tenant_id=self._tenant_id,
                    driver_id_column=Driver.id,
                    truck_id=truck_id,
                    competencia_mes=competencia_mes,
                    competencia_ano=competencia_ano,
                )
            )
        total = await self._count(query)
        result = await self._session.execute(
            query.order_by(Driver.nome).offset(params.offset).limit(params.limit)
        )
        return list(result.scalars().all()), total

    async def count_active(
        self,
        *,
        driver_id: uuid.UUID | None = None,
        truck_id: uuid.UUID | None = None,
        client_id: uuid.UUID | None = None,
        competencia_mes: int | None = None,
        competencia_ano: int | None = None,
        period_from: date | None = None,
        period_to: date | None = None,
    ) -> int:
        """Motoristas ativos, opcionalmente restritos por frete matching."""
        query = select(func.count(Driver.id)).where(
            Driver.deleted_at.is_(None),
            Driver.tenant_id == self._tenant_id,
            Driver.status == DriverStatus.ATIVO,
        )
        if driver_id is not None:
            query = query.where(Driver.id == driver_id)
        elif (
            truck_id is not None
            or client_id is not None
            or competencia_mes is not None
            or period_from is not None
            or period_to is not None
        ):
            query = query.where(
                matching_freight_exists(
                    tenant_id=self._tenant_id,
                    driver_id_column=Driver.id,
                    truck_id=truck_id,
                    client_id=client_id,
                    competencia_mes=competencia_mes,
                    competencia_ano=competencia_ano,
                    period_from=period_from,
                    period_to=period_to,
                )
            )
        result = await self._session.execute(query)
        return int(result.scalar_one() or 0)

    async def hard_delete(self, driver: Driver) -> None:
        """Remove motorista; abastecimentos/pedágios/fretes preservam histórico (FK SET NULL)."""
        await self._session.delete(driver)
        await self._session.flush()
