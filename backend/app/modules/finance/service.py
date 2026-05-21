"""Finance service."""
from __future__ import annotations

import uuid
from datetime import date

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.finance.models import FinanceEntry
from app.modules.finance.repository import FinanceRepository
from app.modules.finance.schemas import (
    CashFlowResponse,
    FinanceEntryCreate,
    FinanceEntryUpdate,
)
from app.modules.users.models import User
from app.shared.enums import FinanceEntryStatus, FinanceEntryType, UserRole
from app.shared.exceptions.custom import ForbiddenException, NotFoundException
from app.shared.pagination import PagedResponse, PageParams

log = structlog.get_logger(__name__)


class FinanceService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = FinanceRepository(session)

    def _check_access(self, user: User) -> None:
        if user.role not in (UserRole.ADMIN, UserRole.FINANCEIRO):
            raise ForbiddenException("Acesso restrito ao módulo financeiro")

    async def create(self, data: FinanceEntryCreate, created_by: User) -> FinanceEntry:
        self._check_access(created_by)
        entry = FinanceEntry(**data.model_dump())
        entry = await self._repo.create(entry)
        await self._session.commit()
        log.info("finance_entry_created", entry_id=str(entry.id), tipo=data.tipo.value)
        return entry

    async def get_by_id(self, entry_id: uuid.UUID, requesting_user: User) -> FinanceEntry:
        self._check_access(requesting_user)
        entry = await self._repo.get_by_id(entry_id)
        if not entry:
            raise NotFoundException("Lançamento não encontrado")
        return entry

    async def list(
        self,
        params: PageParams,
        requesting_user: User,
        tipo: FinanceEntryType | None = None,
        status: FinanceEntryStatus | None = None,
        categoria: str | None = None,
        freight_id: uuid.UUID | None = None,
        vencimento_from: date | None = None,
        vencimento_to: date | None = None,
    ) -> PagedResponse[FinanceEntry]:
        self._check_access(requesting_user)
        items, total = await self._repo.list(
            params, tipo, status, categoria, freight_id, vencimento_from, vencimento_to
        )
        return PagedResponse.create(items, total, params)

    async def update(self, entry_id: uuid.UUID, data: FinanceEntryUpdate, updated_by: User) -> FinanceEntry:
        self._check_access(updated_by)
        entry = await self._repo.get_by_id(entry_id)
        if not entry:
            raise NotFoundException("Lançamento não encontrado")
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(entry, field, value)
        entry = await self._repo.update(entry)
        await self._session.commit()
        return entry

    async def delete(self, entry_id: uuid.UUID, deleted_by: User) -> None:
        self._check_access(deleted_by)
        entry = await self._repo.get_by_id(entry_id)
        if not entry:
            raise NotFoundException("Lançamento não encontrado")
        await self._repo.soft_delete(entry)
        await self._session.commit()

    async def get_cash_flow(self, requesting_user: User) -> CashFlowResponse:
        self._check_access(requesting_user)
        summary = await self._repo.get_cash_flow_summary()
        return CashFlowResponse(**summary)
