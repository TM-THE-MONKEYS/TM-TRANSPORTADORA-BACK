"""Driver repository."""
from __future__ import annotations

import uuid
from datetime import timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.drivers.models import Driver
from app.shared.base_repository import TenantBaseRepository
from app.shared.enums import DriverStatus
from app.shared.pagination import PageParams
from app.shared.utils.dates import today_sp

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
    ) -> tuple[list[Driver], int]:
        query = self._base_query()
        if status:
            query = query.where(Driver.status == status)
        if search:
            term = f"%{search}%"
            query = query.where(
                Driver.nome.ilike(term) | Driver.cpf.ilike(term) | Driver.cnh.ilike(term)
            )
        total = await self._count(query)
        result = await self._session.execute(
            query.order_by(Driver.nome).offset(params.offset).limit(params.limit)
        )
        return list(result.scalars().all()), total

    async def list_cnh_alerts(self, days_ahead: int = 30) -> list[Driver]:
        """CNH vencida ou a vencer em até days_ahead dias."""
        today = today_sp()
        limit = today + timedelta(days=days_ahead)
        result = await self._session.execute(
            self._base_query()
            .where(
                Driver.cnh_expiry.isnot(None),
                Driver.cnh_expiry <= limit,
            )
            .order_by(Driver.cnh_expiry.asc())
        )
        return list(result.scalars().all())

    async def count_cnh_alerts(self, days_ahead: int = 30) -> int:
        return len(await self.list_cnh_alerts(days_ahead))

    async def hard_delete(self, driver: Driver) -> None:
        """Remove motorista; abastecimentos/pedágios/fretes preservam histórico (FK SET NULL)."""
        await self._session.delete(driver)
        await self._session.flush()
