"""Competência mensal — filtros SQL reutilizáveis."""
from __future__ import annotations

from calendar import monthrange
from datetime import date

from sqlalchemy import ColumnElement, extract, or_
from sqlalchemy.sql import Select

from app.modules.finance.models import FinanceEntry


def freight_competencia_filter_clause(year: int, month: int) -> ColumnElement[bool]:
    """Filtra fretes pela competência: data_entrega_real → data_entrega_prevista → created_at.

    Mesma lógica de fallback do financeiro (melhor data disponível).
    Importa Freight de forma lazy para evitar dependência circular.
    """
    from app.modules.freights.models import Freight  # noqa: PLC0415

    return or_(
        # 1. Entrega real no mês
        (
            Freight.data_entrega_real.isnot(None)
            & (extract("year", Freight.data_entrega_real) == year)
            & (extract("month", Freight.data_entrega_real) == month)
        ),
        # 2. Sem entrega real → entrega prevista no mês
        (
            Freight.data_entrega_real.is_(None)
            & Freight.data_entrega_prevista.isnot(None)
            & (extract("year", Freight.data_entrega_prevista) == year)
            & (extract("month", Freight.data_entrega_prevista) == month)
        ),
        # 3. Sem nenhuma data → mês de criação
        (
            Freight.data_entrega_real.is_(None)
            & Freight.data_entrega_prevista.is_(None)
            & (extract("year", Freight.created_at) == year)
            & (extract("month", Freight.created_at) == month)
        ),
    )


def competencia_bounds(year: int, month: int) -> tuple[date, date]:
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    return first, last


def competencia_filter_clause(year: int, month: int) -> ColumnElement[bool]:
    """Filtra lançamentos pela competência: vencimento → pagamento → mês de criação."""
    first, last = competencia_bounds(year, month)
    return or_(
        FinanceEntry.data_vencimento.between(first, last),
        (
            FinanceEntry.data_vencimento.is_(None)
            & FinanceEntry.data_pagamento.between(first, last)
        ),
        (
            FinanceEntry.data_vencimento.is_(None)
            & FinanceEntry.data_pagamento.is_(None)
            & (extract("year", FinanceEntry.created_at) == year)
            & (extract("month", FinanceEntry.created_at) == month)
        ),
    )


def apply_competencia_filter(query: Select, year: int, month: int) -> Select:
    return query.where(competencia_filter_clause(year, month))
