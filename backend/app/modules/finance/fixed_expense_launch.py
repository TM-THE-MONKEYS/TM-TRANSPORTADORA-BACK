"""Helpers for launching fixed expenses (manual + automatic)."""
from __future__ import annotations

import uuid
from calendar import monthrange
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.finance.models import FinanceEntry, FixedExpense
from app.modules.finance.fixed_expense_utils import is_expired, refresh_expiry
from app.modules.finance.repository import FinanceRepository
from app.shared.enums import FinanceEntryStatus, FinanceEntryType
from app.shared.exceptions.custom import ValidationException
from app.shared.utils.dates import month_bounds, today_sp

FIXED_EXPENSE_SOURCE_PREFIX = "fixed_expense:"


def fixed_expense_month_key(expense_id: uuid.UUID, year: int, month: int) -> str:
    return f"{FIXED_EXPENSE_SOURCE_PREFIX}{expense_id}:{year:04d}-{month:02d}"


def legacy_fixed_expense_key(expense_id: uuid.UUID) -> str:
    return f"{FIXED_EXPENSE_SOURCE_PREFIX}{expense_id}"


def resolve_vencimento(expense: FixedExpense, reference: date) -> date:
    if expense.dia_vencimento:
        try:
            return reference.replace(day=expense.dia_vencimento)
        except ValueError:
            last = monthrange(reference.year, reference.month)[1]
            return reference.replace(day=min(expense.dia_vencimento, last))
    return reference


async def find_launch_for_month(
    session: AsyncSession,
    expense_id: uuid.UUID,
    year: int,
    month: int,
) -> FinanceEntry | None:
    month_key = fixed_expense_month_key(expense_id, year, month)
    result = await session.execute(
        select(FinanceEntry).where(
            FinanceEntry.deleted_at.is_(None),
            FinanceEntry.observacoes == month_key,
        )
    )
    entry = result.scalar_one_or_none()
    if entry:
        return entry

    first, last = month_bounds(year, month)
    legacy_key = legacy_fixed_expense_key(expense_id)
    result = await session.execute(
        select(FinanceEntry).where(
            FinanceEntry.deleted_at.is_(None),
            FinanceEntry.observacoes == legacy_key,
            FinanceEntry.data_vencimento >= first,
            FinanceEntry.data_vencimento <= last,
        )
    )
    return result.scalar_one_or_none()


async def launch_fixed_expense_for_month(
    session: AsyncSession,
    expense: FixedExpense,
    *,
    reference: date | None = None,
    increment_parcel: bool = True,
) -> FinanceEntry | None:
    """Create finance entry for fixed expense in reference month (idempotent)."""
    refresh_expiry(expense)
    if not expense.ativo or is_expired(expense):
        return None

    ref = reference or today_sp()
    existing = await find_launch_for_month(session, expense.id, ref.year, ref.month)
    if existing:
        return existing

    vencimento = resolve_vencimento(expense, ref)
    month_key = fixed_expense_month_key(expense.id, ref.year, ref.month)

    entry = FinanceEntry(
        tipo=FinanceEntryType.DESPESA,
        categoria=expense.categoria,
        descricao=f"Gasto fixo: {expense.nome}",
        valor=float(expense.valor),
        status=FinanceEntryStatus.PENDENTE,
        data_vencimento=vencimento,
        observacoes=month_key,
        tenant_id=expense.tenant_id,
    )
    entry = await FinanceRepository(session, expense.tenant_id).create(entry)

    if increment_parcel:
        expense.parcelas_lancadas += 1
        refresh_expiry(expense)

    return entry


async def launch_fixed_expense_manual(
    session: AsyncSession,
    expense: FixedExpense,
    vencimento: date | None = None,
) -> FinanceEntry:
    """Manual launch from UI — idempotent per competence month."""
    refresh_expiry(expense)
    if not expense.ativo or is_expired(expense):
        raise ValidationException("Gasto fixo inativo ou expirado — lançamento não permitido")

    ref = vencimento or today_sp()
    existing = await find_launch_for_month(session, expense.id, ref.year, ref.month)
    if existing:
        return existing

    entry = await launch_fixed_expense_for_month(
        session,
        expense,
        reference=ref,
        increment_parcel=True,
    )
    if not entry:
        raise ValidationException("Gasto fixo inativo ou expirado — lançamento não permitido")
    return entry
