"""Finance repository."""
from __future__ import annotations

import uuid
from datetime import date

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.finance.models import FinanceEntry
from app.shared.base_repository import TenantBaseRepository
from app.shared.enums import FinanceEntryStatus, FinanceEntryType
from app.shared.pagination import PageParams

log = structlog.get_logger(__name__)


class FinanceRepository(TenantBaseRepository[FinanceEntry]):
    model = FinanceEntry

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        super().__init__(session, tenant_id)

    async def list(
        self,
        params: PageParams,
        tipo: FinanceEntryType | None = None,
        status: FinanceEntryStatus | None = None,
        categoria: str | None = None,
        freight_id: uuid.UUID | None = None,
        vencimento_from: date | None = None,
        vencimento_to: date | None = None,
    ) -> tuple[list[FinanceEntry], int]:
        query = self._base_query()
        if tipo:
            query = query.where(FinanceEntry.tipo == tipo)
        if status:
            query = query.where(FinanceEntry.status == status)
        if categoria:
            query = query.where(FinanceEntry.categoria.ilike(f"%{categoria}%"))
        if freight_id:
            query = query.where(FinanceEntry.freight_id == freight_id)
        if vencimento_from:
            query = query.where(FinanceEntry.data_vencimento >= vencimento_from)
        if vencimento_to:
            query = query.where(FinanceEntry.data_vencimento <= vencimento_to)
        total = await self._count(query)
        result = await self._session.execute(
            query.order_by(FinanceEntry.created_at.desc()).offset(params.offset).limit(params.limit)
        )
        return list(result.scalars().all()), total

    async def get_cash_flow_summary(self) -> dict[str, float]:
        result = await self._session.execute(
            select(
                FinanceEntry.tipo,
                FinanceEntry.status,
                func.sum(FinanceEntry.valor).label("total"),
            )
            .where(FinanceEntry.deleted_at.is_(None), FinanceEntry.tenant_id == self._tenant_id)
            .group_by(FinanceEntry.tipo, FinanceEntry.status)
        )
        summary: dict[str, float] = {
            "total_receitas": 0.0,
            "total_despesas": 0.0,
            "receitas_pendentes": 0.0,
            "despesas_pendentes": 0.0,
            "receitas_pagas": 0.0,
            "despesas_pagas": 0.0,
        }
        for tipo, status, total in result.all():
            val = float(total or 0.0)
            if tipo == FinanceEntryType.RECEITA:
                summary["total_receitas"] += val
                if status == FinanceEntryStatus.PENDENTE:
                    summary["receitas_pendentes"] += val
                elif status == FinanceEntryStatus.PAGO:
                    summary["receitas_pagas"] += val
            elif tipo == FinanceEntryType.DESPESA:
                summary["total_despesas"] += val
                if status == FinanceEntryStatus.PENDENTE:
                    summary["despesas_pendentes"] += val
                elif status == FinanceEntryStatus.PAGO:
                    summary["despesas_pagas"] += val
        summary["saldo"] = summary["total_receitas"] - summary["total_despesas"]
        return summary
