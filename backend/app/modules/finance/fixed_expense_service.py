"""Fixed expense service."""
from __future__ import annotations

import uuid
from datetime import date

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.finance.fixed_expense_repository import FixedExpenseRepository
from app.modules.finance.fixed_expense_schemas import FixedExpenseCreate, FixedExpenseUpdate
from app.modules.finance.fixed_expense_utils import is_expired, refresh_expiry
from app.modules.finance.models import FinanceEntry, FixedExpense
from app.modules.finance.repository import FinanceRepository
from app.modules.users.models import User
from app.shared.enums import FinanceEntryStatus, FinanceEntryType, UserRole
from app.shared.exceptions.custom import ForbiddenException, NotFoundException, ValidationException

log = structlog.get_logger(__name__)

_WRITE_ROLES = frozenset({UserRole.ADMIN, UserRole.FINANCEIRO})
_READ_ROLES = frozenset({UserRole.ADMIN, UserRole.FINANCEIRO, UserRole.OPERADOR})


class FixedExpenseService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._repo = FixedExpenseRepository(session, tenant_id)
        self._finance_repo = FinanceRepository(session, tenant_id)

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

    async def launch(self, expense_id: uuid.UUID, launched_by: User) -> FinanceEntry:
        self._check_write(launched_by)
        expense = await self._refresh_and_get(expense_id)
        if not expense.ativo or is_expired(expense):
            raise ValidationException(
                "Gasto fixo inativo ou expirado — lançamento não permitido"
            )

        vencimento: date | None = None
        if expense.dia_vencimento:
            today = date.today()
            try:
                vencimento = today.replace(day=expense.dia_vencimento)
            except ValueError:
                vencimento = today

        entry = FinanceEntry(
            tipo=FinanceEntryType.DESPESA,
            categoria=expense.categoria,
            descricao=f"Gasto fixo: {expense.nome}",
            valor=float(expense.valor),
            status=FinanceEntryStatus.PENDENTE,
            data_vencimento=vencimento,
            observacoes=f"fixed_expense:{expense.id}",
            tenant_id=self._tenant_id,
        )
        entry = await self._finance_repo.create(entry)

        expense.parcelas_lancadas += 1
        refresh_expiry(expense)
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
