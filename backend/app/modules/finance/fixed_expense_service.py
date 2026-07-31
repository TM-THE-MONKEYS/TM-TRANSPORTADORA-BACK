"""Fixed expense service."""
from __future__ import annotations

import uuid
from datetime import date

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.finance.competencia_schemas import (
    FixedExpenseLaunchStatusItem,
    LaunchPendingResponse,
)
from app.modules.finance.fixed_expense_launch import (
    find_launch_for_month,
    launch_fixed_expense_for_month,
    launch_fixed_expense_manual,
    resolve_vencimento,
)
from app.modules.finance.fixed_expense_repository import FixedExpenseRepository
from app.modules.finance.fixed_expense_schemas import FixedExpenseCreate, FixedExpenseUpdate
from app.modules.finance.fixed_expense_utils import refresh_expiry
from app.modules.finance.models import FinanceEntry, FixedExpense
from app.modules.users.models import User
from app.shared.enums import UserRole
from app.shared.exceptions.custom import ForbiddenException, NotFoundException
from app.shared.utils.dates import normalize_date_only_value, today_sp

log = structlog.get_logger(__name__)

_WRITE_ROLES = frozenset({UserRole.ADMIN, UserRole.FINANCEIRO})
_READ_ROLES = frozenset({UserRole.ADMIN, UserRole.FINANCEIRO, UserRole.OPERADOR})


class FixedExpenseService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._repo = FixedExpenseRepository(session, tenant_id)

    def _check_read(self, user: User) -> None:
        if user.role not in _READ_ROLES:
            raise ForbiddenException("Acesso restrito ao módulo financeiro")

    def _check_write(self, user: User) -> None:
        if user.role not in _WRITE_ROLES:
            raise ForbiddenException("Acesso restrito para alterar gastos fixos")

    async def _refresh_and_get(self, expense_id: uuid.UUID) -> FixedExpense:
        expense = await self._repo.get_by_id(expense_id)
        if not expense:
            raise NotFoundException("Gasto fixo não encontrado")
        refresh_expiry(expense)
        return expense

    async def list(self, requesting_user: User) -> list[FixedExpense]:
        self._check_read(requesting_user)
        items = await self._repo.list_active()
        changed = False
        for item in items:
            if refresh_expiry(item):
                changed = True
        if changed:
            await self._session.commit()
        return items

    async def create(self, data: FixedExpenseCreate, created_by: User) -> FixedExpense:
        self._check_write(created_by)
        expense = FixedExpense(**data.model_dump())
        expense = await self._repo.create(expense)
        await self._session.commit()
        log.info("fixed_expense_created", expense_id=str(expense.id))
        return expense

    async def update(
        self, expense_id: uuid.UUID, data: FixedExpenseUpdate, updated_by: User
    ) -> FixedExpense:
        self._check_write(updated_by)
        expense = await self._refresh_and_get(expense_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(expense, field, value)
        refresh_expiry(expense)
        expense = await self._repo.update(expense)
        await self._session.commit()
        return expense

    async def launch(
        self,
        expense_id: uuid.UUID,
        launched_by: User,
        vencimento: date | None = None,
    ) -> FinanceEntry:
        self._check_write(launched_by)
        expense = await self._refresh_and_get(expense_id)
        ref = normalize_date_only_value(vencimento) if vencimento else today_sp()
        entry = await launch_fixed_expense_manual(self._session, expense, vencimento=ref)
        await self._repo.update(expense)
        await self._session.commit()
        log.info(
            "fixed_expense_launched",
            expense_id=str(expense.id),
            entry_id=str(entry.id),
            parcelas=expense.parcelas_lancadas,
        )
        return entry

    async def delete(self, expense_id: uuid.UUID, deleted_by: User) -> None:
        self._check_write(deleted_by)
        expense = await self._refresh_and_get(expense_id)
        await self._repo.soft_delete(expense)
        await self._session.commit()
        log.info("fixed_expense_deleted", expense_id=str(expense.id))

    async def launch_status(
        self,
        requesting_user: User,
        competencia_mes: int,
        competencia_ano: int,
    ) -> list[FixedExpenseLaunchStatusItem]:
        self._check_read(requesting_user)
        items = await self.list(requesting_user)
        ref = date(competencia_ano, competencia_mes, 1)
        result: list[FixedExpenseLaunchStatusItem] = []
        for expense in items:
            if not expense.ativo:
                continue
            linked = await find_launch_for_month(
                self._session, expense.id, competencia_ano, competencia_mes
            )
            result.append(
                FixedExpenseLaunchStatusItem(
                    id=expense.id,
                    nome=expense.nome,
                    categoria=expense.categoria,
                    valor=float(expense.valor),
                    ativo=expense.ativo,
                    launched_this_month=linked is not None,
                    linked_entry_id=linked.id if linked else None,
                    suggested_vencimento=resolve_vencimento(expense, ref),
                )
            )
        return result

    async def launch_pending(
        self,
        launched_by: User,
        competencia_mes: int,
        competencia_ano: int,
    ) -> LaunchPendingResponse:
        self._check_write(launched_by)
        ref = date(competencia_ano, competencia_mes, 1)
        items = await self._repo.list_active()
        launched = 0
        skipped = 0
        for expense in items:
            refresh_expiry(expense)
            if not expense.ativo:
                skipped += 1
                continue
            existing = await find_launch_for_month(
                self._session, expense.id, competencia_ano, competencia_mes
            )
            if existing:
                skipped += 1
                continue
            before = expense.parcelas_lancadas
            entry = await launch_fixed_expense_for_month(
                self._session, expense, reference=ref, increment_parcel=True
            )
            if entry and expense.parcelas_lancadas > before:
                launched += 1
                await self._repo.update(expense)
            else:
                skipped += 1
        await self._session.commit()
        return LaunchPendingResponse(launched_count=launched, skipped_count=skipped)
