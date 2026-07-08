"""Finance service."""
from __future__ import annotations

import uuid
from datetime import date

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.finance.models import FinanceEntry
from app.modules.finance.repository import FinanceRepository
from app.modules.finance.competencia_schemas import CompetenciaReportResponse
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

_READ_ROLES = frozenset({UserRole.ADMIN, UserRole.FINANCEIRO, UserRole.OPERADOR})
_WRITE_ROLES = frozenset({UserRole.ADMIN, UserRole.FINANCEIRO})


class FinanceService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._repo = FinanceRepository(session, tenant_id)

    def _check_read_access(self, user: User) -> None:
        if user.role not in _READ_ROLES:
            raise ForbiddenException("Acesso restrito ao módulo financeiro")

    def _check_write_access(self, user: User) -> None:
        if user.role not in _WRITE_ROLES:
            raise ForbiddenException("Acesso restrito para alterar lançamentos financeiros")

    async def create(self, data: FinanceEntryCreate, created_by: User) -> FinanceEntry:
        self._check_write_access(created_by)
        entry = FinanceEntry(**data.model_dump())
        entry = await self._repo.create(entry)
        await self._session.commit()
        log.info("finance_entry_created", entry_id=str(entry.id), tipo=data.tipo.value)
        return entry

    async def get_by_id(self, entry_id: uuid.UUID, requesting_user: User) -> FinanceEntry:
        self._check_read_access(requesting_user)
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
        competencia_mes: int | None = None,
        competencia_ano: int | None = None,
    ) -> PagedResponse[FinanceEntry]:
        self._check_read_access(requesting_user)
        items, total = await self._repo.list(
            params,
            tipo,
            status,
            categoria,
            freight_id,
            vencimento_from,
            vencimento_to,
            competencia_mes,
            competencia_ano,
        )
        return PagedResponse.create(items, total, params)

    async def update(self, entry_id: uuid.UUID, data: FinanceEntryUpdate, updated_by: User) -> FinanceEntry:
        self._check_write_access(updated_by)
        entry = await self._repo.get_by_id(entry_id)
        if not entry:
            raise NotFoundException("Lançamento não encontrado")
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(entry, field, value)
        entry = await self._repo.update(entry)
        await self._session.commit()
        return entry

    async def delete(self, entry_id: uuid.UUID, deleted_by: User) -> None:
        self._check_write_access(deleted_by)
        entry = await self._repo.get_by_id(entry_id)
        if not entry:
            raise NotFoundException("Lançamento não encontrado")
        await self._repo.soft_delete(entry)
        await self._session.commit()

    async def get_cash_flow(
        self,
        requesting_user: User,
        competencia_mes: int | None = None,
        competencia_ano: int | None = None,
    ) -> CashFlowResponse:
        self._check_read_access(requesting_user)
        summary = await self._repo.get_cash_flow_summary(competencia_mes, competencia_ano)
        return CashFlowResponse(**summary)

    async def get_competencia_report(
        self,
        requesting_user: User,
        competencia_mes: int,
        competencia_ano: int,
    ) -> CompetenciaReportResponse:
        self._check_read_access(requesting_user)
        summary = await self._repo.get_cash_flow_summary(competencia_mes, competencia_ano)
        daily, by_category = await self._repo.get_competencia_aggregates(
            competencia_mes, competencia_ano
        )
        daily_series = [
            {
                "date": d,
                "receitas": vals["receitas"],
                "despesas": vals["despesas"],
            }
            for d, vals in sorted(daily.items())
        ]
        expenses_by_category = [
            {"categoria": cat, "valor": val}
            for cat, val in sorted(by_category.items(), key=lambda x: -x[1])
        ]
        return CompetenciaReportResponse(
            competencia_mes=competencia_mes,
            competencia_ano=competencia_ano,
            cash_flow=CashFlowResponse(**summary),
            daily_series=daily_series,  # type: ignore[arg-type]
            expenses_by_category=expenses_by_category,  # type: ignore[arg-type]
        )

    async def sync_from_freights(self, requesting_user: User) -> dict[str, int]:
        """Importa receitas de fretes e despesas (abastecimentos/custos) para o financeiro."""
        self._check_write_access(requesting_user)
        from app.modules.finance.freight_sync import sync_all_from_freights

        stats = await sync_all_from_freights(self._session, self._tenant_id)
        await self._session.commit()
        log.info("finance_sync_from_freights", **stats)
        return stats
