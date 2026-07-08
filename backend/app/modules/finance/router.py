"""Finance routes."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from starlette.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_active_user
from app.api.v1.dependencies.database import get_db
from app.modules.finance.competencia_schemas import (
    CompetenciaReportResponse,
    FixedExpenseLaunchStatusItem,
    LaunchPendingResponse,
)
from app.modules.finance.schemas import (
    CashFlowResponse,
    FinanceEntryCreate,
    FinanceEntryListResponse,
    FinanceEntryRead,
    FinanceEntryUpdate,
)
from app.modules.finance.fixed_expense_schemas import (
    FixedExpenseCreate,
    FixedExpenseLaunch,
    FixedExpenseRead,
    FixedExpenseUpdate,
)
from app.modules.finance.fixed_expense_service import FixedExpenseService
from app.modules.finance.service import FinanceService
from app.modules.users.models import User
from app.shared.enums import FinanceEntryStatus, FinanceEntryType
from app.shared.pagination import PagedResponse, PageParams

router = APIRouter(prefix="/finance", tags=["finance"])


@router.post("/sync-from-freights")
async def sync_finance_from_freights(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> dict[str, int]:
    """Gera receitas/despesas a partir de fretes, abastecimentos e custos existentes."""
    service = FinanceService(db, current_user.tenant_id)
    return await service.sync_from_freights(current_user)


@router.get("/cash-flow", response_model=CashFlowResponse)
async def get_cash_flow(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    competencia_mes: int | None = Query(default=None, ge=1, le=12),
    competencia_ano: int | None = Query(default=None, ge=2000, le=2100),
) -> CashFlowResponse:
    service = FinanceService(db, current_user.tenant_id)
    return await service.get_cash_flow(current_user, competencia_mes, competencia_ano)


@router.get("/competencia-report", response_model=CompetenciaReportResponse)
async def get_competencia_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    competencia_mes: int = Query(ge=1, le=12),
    competencia_ano: int = Query(ge=2000, le=2100),
) -> CompetenciaReportResponse:
    service = FinanceService(db, current_user.tenant_id)
    return await service.get_competencia_report(current_user, competencia_mes, competencia_ano)


@router.get("/fixed-expenses", response_model=list[FixedExpenseRead])
async def list_fixed_expenses(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[FixedExpenseRead]:
    service = FixedExpenseService(db, current_user.tenant_id)
    return await service.list(current_user)  # type: ignore[return-value]


@router.get("/fixed-expenses/launch-status", response_model=list[FixedExpenseLaunchStatusItem])
async def fixed_expenses_launch_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    competencia_mes: int = Query(ge=1, le=12),
    competencia_ano: int = Query(ge=2000, le=2100),
) -> list[FixedExpenseLaunchStatusItem]:
    service = FixedExpenseService(db, current_user.tenant_id)
    return await service.launch_status(current_user, competencia_mes, competencia_ano)


@router.post("/fixed-expenses/launch-pending", response_model=LaunchPendingResponse)
async def launch_pending_fixed_expenses(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    competencia_mes: int = Query(ge=1, le=12),
    competencia_ano: int = Query(ge=2000, le=2100),
) -> LaunchPendingResponse:
    service = FixedExpenseService(db, current_user.tenant_id)
    return await service.launch_pending(current_user, competencia_mes, competencia_ano)


@router.post("/fixed-expenses", response_model=FixedExpenseRead, status_code=status.HTTP_201_CREATED)
async def create_fixed_expense(
    payload: FixedExpenseCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> FixedExpenseRead:
    service = FixedExpenseService(db, current_user.tenant_id)
    return await service.create(payload, current_user)  # type: ignore[return-value]


@router.patch("/fixed-expenses/{expense_id}", response_model=FixedExpenseRead)
async def update_fixed_expense(
    expense_id: uuid.UUID,
    payload: FixedExpenseUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> FixedExpenseRead:
    service = FixedExpenseService(db, current_user.tenant_id)
    return await service.update(expense_id, payload, current_user)  # type: ignore[return-value]


@router.post("/fixed-expenses/{expense_id}/launch", response_model=FinanceEntryRead)
async def launch_fixed_expense(
    expense_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    payload: FixedExpenseLaunch | None = None,
) -> FinanceEntryRead:
    service = FixedExpenseService(db, current_user.tenant_id)
    vencimento = payload.data_vencimento if payload else None
    entry = await service.launch(expense_id, current_user, vencimento=vencimento)
    return FinanceEntryRead.model_validate(entry)


@router.get("", response_model=PagedResponse[FinanceEntryListResponse])
async def list_finance_entries(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    tipo: FinanceEntryType | None = Query(default=None),
    status: FinanceEntryStatus | None = Query(default=None),
    categoria: str | None = Query(default=None, max_length=100),
    freight_id: uuid.UUID | None = Query(default=None),
    vencimento_from: date | None = Query(default=None),
    vencimento_to: date | None = Query(default=None),
    competencia_mes: int | None = Query(default=None, ge=1, le=12),
    competencia_ano: int | None = Query(default=None, ge=2000, le=2100),
) -> PagedResponse[FinanceEntryListResponse]:
    service = FinanceService(db, current_user.tenant_id)
    params = PageParams(page=page, size=size)
    return await service.list(  # type: ignore[return-value]
        params,
        current_user,
        tipo,
        status,
        categoria,
        freight_id,
        vencimento_from,
        vencimento_to,
        competencia_mes,
        competencia_ano,
    )


@router.post("", response_model=FinanceEntryRead, status_code=status.HTTP_201_CREATED)
async def create_finance_entry(
    payload: FinanceEntryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> FinanceEntryRead:
    service = FinanceService(db, current_user.tenant_id)
    return await service.create(payload, current_user)  # type: ignore[return-value]


@router.get("/{entry_id}", response_model=FinanceEntryRead)
async def get_finance_entry(
    entry_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> FinanceEntryRead:
    service = FinanceService(db, current_user.tenant_id)
    return await service.get_by_id(entry_id, current_user)  # type: ignore[return-value]


@router.patch("/{entry_id}", response_model=FinanceEntryRead)
async def update_finance_entry(
    entry_id: uuid.UUID,
    payload: FinanceEntryUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> FinanceEntryRead:
    service = FinanceService(db, current_user.tenant_id)
    return await service.update(entry_id, payload, current_user)  # type: ignore[return-value]


@router.delete(
    "/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_finance_entry(
    entry_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Response:
    service = FinanceService(db, current_user.tenant_id)
    await service.delete(entry_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
