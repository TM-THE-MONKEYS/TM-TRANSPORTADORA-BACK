"""Dashboard routes."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_active_user
from app.api.v1.dependencies.competencia import OptionalCompetenciaDep
from app.api.v1.dependencies.database import get_db
from app.modules.dashboard.schemas import (
    DashboardKPIsFrontend,
    FreightStatusCount,
    RevenuePoint,
)
from app.modules.dashboard.service import DashboardService
from app.modules.users.models import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/kpis", response_model=DashboardKPIsFrontend)
async def get_dashboard_kpis(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    competencia: OptionalCompetenciaDep,
    # branch_id: aceito para não quebrar o client; sem coluna no banco
    # (branches deferred). Isolamento já é por tenant_id.
    branch_id: uuid.UUID | None = Query(default=None),
    client_id: uuid.UUID | None = Query(default=None),
    truck_id: uuid.UUID | None = Query(default=None),
    driver_id: uuid.UUID | None = Query(default=None),
    period_from: date | None = Query(default=None),
    period_to: date | None = Query(default=None),
) -> DashboardKPIsFrontend:
    service = DashboardService(db, current_user.tenant_id)
    return await service.get_kpis(
        current_user,
        branch_id=branch_id,
        client_id=client_id,
        truck_id=truck_id,
        driver_id=driver_id,
        period_from=period_from,
        period_to=period_to,
        competencia_mes=competencia.mes,
        competencia_ano=competencia.ano,
    )


@router.get("/freights-by-status", response_model=list[FreightStatusCount])
async def get_freights_by_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    competencia: OptionalCompetenciaDep,
    branch_id: uuid.UUID | None = Query(default=None),
    client_id: uuid.UUID | None = Query(default=None),
    truck_id: uuid.UUID | None = Query(default=None),
    driver_id: uuid.UUID | None = Query(default=None),
    period_from: date | None = Query(default=None),
    period_to: date | None = Query(default=None),
) -> list[FreightStatusCount]:
    service = DashboardService(db, current_user.tenant_id)
    return await service.get_freights_by_status(
        current_user,
        branch_id=branch_id,
        client_id=client_id,
        truck_id=truck_id,
        driver_id=driver_id,
        period_from=period_from,
        period_to=period_to,
        competencia_mes=competencia.mes,
        competencia_ano=competencia.ano,
    )


@router.get("/revenue-series", response_model=list[RevenuePoint])
async def get_revenue_series(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    days: int = Query(default=30, ge=1, le=365),
) -> list[RevenuePoint]:
    service = DashboardService(db, current_user.tenant_id)
    return await service.get_revenue_series(current_user, days)
