"""Finance repository."""
from __future__ import annotations

import uuid
from calendar import monthrange
from datetime import date, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.finance.models import FinanceEntry
from app.shared.base_repository import TenantBaseRepository
from app.shared.enums import FinanceEntryStatus, FinanceEntryType
from app.shared.filters.competencia import apply_competencia_filter, competencia_bounds
from app.shared.pagination import PageParams

log = structlog.get_logger(__name__)


def _entry_competencia_date(entry: FinanceEntry) -> date | None:
    if entry.data_vencimento:
        return entry.data_vencimento
    if entry.data_pagamento:
        return entry.data_pagamento
    if entry.created_at:
        return entry.created_at.date()
    return None


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
        competencia_mes: int | None = None,
        competencia_ano: int | None = None,
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
        if competencia_mes and competencia_ano:
            query = apply_competencia_filter(query, competencia_ano, competencia_mes)
        total = await self._count(query)
        result = await self._session.execute(
            query.order_by(FinanceEntry.created_at.desc()).offset(params.offset).limit(params.limit)
        )
        return list(result.scalars().all()), total

    async def list_for_competencia(
        self, competencia_mes: int, competencia_ano: int
    ) -> list[FinanceEntry]:
        query = apply_competencia_filter(self._base_query(), competencia_ano, competencia_mes)
        result = await self._session.execute(query.order_by(FinanceEntry.created_at.desc()))
        return list(result.scalars().all())

    async def get_cash_flow_summary(
        self,
        competencia_mes: int | None = None,
        competencia_ano: int | None = None,
    ) -> dict[str, float]:
        base = select(
            FinanceEntry.tipo,
            FinanceEntry.status,
            func.sum(FinanceEntry.valor).label("total"),
        ).where(FinanceEntry.deleted_at.is_(None), FinanceEntry.tenant_id == self._tenant_id)

        if competencia_mes and competencia_ano:
            base = apply_competencia_filter(base, competencia_ano, competencia_mes)

        result = await self._session.execute(base.group_by(FinanceEntry.tipo, FinanceEntry.status))
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

    async def get_competencia_aggregates(
        self, competencia_mes: int, competencia_ano: int
    ) -> tuple[dict[str, dict[str, float]], dict[str, float]]:
        """Retorna séries diárias e despesas por categoria para a competência."""
        entries = await self.list_for_competencia(competencia_mes, competencia_ano)
        first, last = competencia_bounds(competencia_ano, competencia_mes)
        daily: dict[str, dict[str, float]] = {}
        day = first
        while day <= last:
            daily[day.isoformat()] = {"receitas": 0.0, "despesas": 0.0}
            day += timedelta(days=1)

        by_category: dict[str, float] = {}
        for entry in entries:
            if entry.status == FinanceEntryStatus.CANCELADO:
                continue
            comp_date = _entry_competencia_date(entry)
            if not comp_date or comp_date < first or comp_date > last:
                continue
            key = comp_date.isoformat()
            val = float(entry.valor)
            if entry.tipo == FinanceEntryType.RECEITA:
                daily[key]["receitas"] += val
            elif entry.tipo == FinanceEntryType.DESPESA:
                daily[key]["despesas"] += val
                by_category[entry.categoria] = by_category.get(entry.categoria, 0.0) + val

        return daily, by_category
