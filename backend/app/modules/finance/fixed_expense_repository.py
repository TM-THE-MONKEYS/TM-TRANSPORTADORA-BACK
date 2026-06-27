"""Fixed expense repository."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.finance.models import FixedExpense
from app.shared.base_repository import TenantBaseRepository


class FixedExpenseRepository(TenantBaseRepository[FixedExpense]):
    model = FixedExpense

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        super().__init__(session, tenant_id)

    async def list_active(self) -> list[FixedExpense]:
        result = await self._session.execute(
            self._base_query().order_by(FixedExpense.nome.asc())
        )
        return list(result.scalars().all())

    async def list_all_for_expiry_check(self) -> list[FixedExpense]:
        """Gastos com limite de parcelas — usado pelo cron de expiração."""
        result = await self._session.execute(
            select(FixedExpense).where(
                FixedExpense.deleted_at.is_(None),
                FixedExpense.ativo.is_(True),
                FixedExpense.total_parcelas.isnot(None),
            )
        )
        return list(result.scalars().all())
