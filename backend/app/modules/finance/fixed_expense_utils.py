"""Regras de vigência para gastos fixos parcelados."""
from __future__ import annotations

from datetime import date, datetime

from app.modules.finance.models import FixedExpense


def effective_start(expense: FixedExpense) -> date:
    if expense.data_inicio:
        return expense.data_inicio
    created = expense.created_at
    if isinstance(created, datetime):
        return created.date()
    return date.today()


def calendar_months_elapsed(start: date, reference: date | None = None) -> int:
    ref = reference or date.today()
    return (ref.year - start.year) * 12 + (ref.month - start.month)


def is_expired_by_parcels(expense: FixedExpense) -> bool:
    if expense.total_parcelas is None:
        return False
    return expense.parcelas_lancadas >= expense.total_parcelas


def is_expired_by_months(expense: FixedExpense, reference: date | None = None) -> bool:
    if expense.total_parcelas is None:
        return False
    return calendar_months_elapsed(effective_start(expense), reference) >= expense.total_parcelas


def is_expired(expense: FixedExpense, reference: date | None = None) -> bool:
    if not expense.ativo:
        return True
    return is_expired_by_parcels(expense) or is_expired_by_months(expense, reference)


def refresh_expiry(expense: FixedExpense, reference: date | None = None) -> bool:
    """Desativa gasto expirado. Retorna True se foi desativado agora."""
    if expense.total_parcelas is None:
        return False
    if expense.ativo and (is_expired_by_parcels(expense) or is_expired_by_months(expense, reference)):
        expense.ativo = False
        return True
    return False
