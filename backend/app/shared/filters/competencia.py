"""Competência mensal — filtros SQL reutilizáveis."""
from __future__ import annotations

import uuid
from calendar import monthrange
from datetime import date

from sqlalchemy import ColumnElement, and_, exists, extract, func, or_, true
from sqlalchemy.sql import Select

from app.modules.finance.models import FinanceEntry
from app.shared.exceptions.custom import BadRequestException

MAX_COMPETENCIA_MONTHS_AHEAD = 2
_COMPETENCIA_AHEAD_MSG = (
    "Não é possível consultar competência mais de 2 meses à frente."
)
_COMPETENCIA_PAIR_MSG = "Informe competencia_mes e competencia_ano juntos."


def is_competencia_within_limit(
    year: int,
    month: int,
    *,
    max_months_ahead: int = MAX_COMPETENCIA_MONTHS_AHEAD,
    today: date | None = None,
) -> bool:
    """True se a competência não ultrapassa today + max_months_ahead.

    Meses no passado são sempre permitidos.
    """
    ref = today or date.today()
    requested = year * 12 + month
    limit = ref.year * 12 + ref.month + max_months_ahead
    return requested <= limit


def validate_competencia_limit(
    year: int,
    month: int,
    *,
    max_months_ahead: int = MAX_COMPETENCIA_MONTHS_AHEAD,
    today: date | None = None,
) -> None:
    if not is_competencia_within_limit(
        year, month, max_months_ahead=max_months_ahead, today=today
    ):
        raise BadRequestException(_COMPETENCIA_AHEAD_MSG)


def resolve_competencia_pair(
    competencia_mes: int | None,
    competencia_ano: int | None,
    *,
    today: date | None = None,
) -> tuple[int | None, int | None]:
    """Exige mês+ano juntos; aplica o limite de 2 meses à frente.

    Ambos None: sem filtro. Só um dos dois: 400.
    """
    if competencia_mes is None and competencia_ano is None:
        return None, None
    if competencia_mes is None or competencia_ano is None:
        raise BadRequestException(_COMPETENCIA_PAIR_MSG)
    validate_competencia_limit(competencia_ano, competencia_mes, today=today)
    return competencia_mes, competencia_ano


def freight_competencia_filter_clause(year: int, month: int) -> ColumnElement[bool]:
    """Filtra fretes pela competência.

    Fallback: data_entrega_real → data_entrega_prevista → created_at.
    Mesma lógica do financeiro. Importa Freight lazy (circular import).
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


def _sql_date_in_range(
    col: ColumnElement[object],
    period_from: date | None,
    period_to: date | None,
) -> ColumnElement[bool]:
    """Compara a parte de data da coluna — portável SQLite + Postgres."""
    col_date = func.date(col)
    parts: list[ColumnElement[bool]] = []
    if period_from is not None:
        parts.append(col_date >= period_from)
    if period_to is not None:
        parts.append(col_date <= period_to)
    if not parts:
        return true()
    return and_(*parts)


def freight_period_filter_clause(
    period_from: date | None,
    period_to: date | None,
) -> ColumnElement[bool]:
    """Intervalo inclusivo com o fallback de competência do frete."""
    from app.modules.freights.models import Freight  # noqa: PLC0415

    return or_(
        (
            Freight.data_entrega_real.isnot(None)
            & _sql_date_in_range(
                Freight.data_entrega_real, period_from, period_to
            )
        ),
        (
            Freight.data_entrega_real.is_(None)
            & Freight.data_entrega_prevista.isnot(None)
            & _sql_date_in_range(
                Freight.data_entrega_prevista, period_from, period_to
            )
        ),
        (
            Freight.data_entrega_real.is_(None)
            & Freight.data_entrega_prevista.is_(None)
            & _sql_date_in_range(Freight.created_at, period_from, period_to)
        ),
    )


def competencia_bounds(year: int, month: int) -> tuple[date, date]:
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    return first, last


def _date_in_range(
    col: ColumnElement[date],
    period_from: date | None,
    period_to: date | None,
) -> ColumnElement[bool]:
    parts: list[ColumnElement[bool]] = []
    if period_from is not None:
        parts.append(col >= period_from)
    if period_to is not None:
        parts.append(col <= period_to)
    if not parts:
        return true()
    return and_(*parts)


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


def finance_period_filter_clause(
    period_from: date | None,
    period_to: date | None,
) -> ColumnElement[bool]:
    """Intervalo em lançamentos: vencimento → pagamento → created_at."""
    return or_(
        (
            FinanceEntry.data_vencimento.isnot(None)
            & _date_in_range(
                FinanceEntry.data_vencimento, period_from, period_to
            )
        ),
        (
            FinanceEntry.data_vencimento.is_(None)
            & FinanceEntry.data_pagamento.isnot(None)
            & _date_in_range(
                FinanceEntry.data_pagamento, period_from, period_to
            )
        ),
        (
            FinanceEntry.data_vencimento.is_(None)
            & FinanceEntry.data_pagamento.is_(None)
            & _sql_date_in_range(
                FinanceEntry.created_at, period_from, period_to
            )
        ),
    )


def apply_competencia_filter(query: Select, year: int, month: int) -> Select:
    return query.where(competencia_filter_clause(year, month))


def matching_freight_exists(
    *,
    tenant_id: uuid.UUID,
    truck_id_column: ColumnElement[uuid.UUID] | None = None,
    driver_id_column: ColumnElement[uuid.UUID] | None = None,
    driver_id: uuid.UUID | None = None,
    truck_id: uuid.UUID | None = None,
    client_id: uuid.UUID | None = None,
    competencia_mes: int | None = None,
    competencia_ano: int | None = None,
    period_from: date | None = None,
    period_to: date | None = None,
) -> ColumnElement[bool]:
    """EXISTS em Freight (mesmo tenant, não deletado) para filtrar frota/motoristas."""
    from app.modules.freights.models import Freight  # noqa: PLC0415

    conds: list[ColumnElement[bool]] = [
        Freight.deleted_at.is_(None),
        Freight.tenant_id == tenant_id,
    ]
    if truck_id_column is not None:
        conds.append(Freight.truck_id == truck_id_column)
    if driver_id_column is not None:
        conds.append(Freight.driver_id == driver_id_column)
    if driver_id is not None:
        conds.append(Freight.driver_id == driver_id)
    if truck_id is not None:
        conds.append(Freight.truck_id == truck_id)
    if client_id is not None:
        conds.append(Freight.client_id == client_id)
    if competencia_mes is not None and competencia_ano is not None:
        conds.append(
            freight_competencia_filter_clause(competencia_ano, competencia_mes)
        )
    elif period_from is not None or period_to is not None:
        conds.append(freight_period_filter_clause(period_from, period_to))
    return exists().where(*conds)
