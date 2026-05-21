"""Dashboard routes."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_active_user
from app.api.v1.dependencies.database import get_db
from app.modules.dashboard.schemas import DashboardKPIs
from app.modules.dashboard.service import DashboardService
from app.modules.users.models import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/kpis", response_model=DashboardKPIs)
async def get_dashboard_kpis(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> DashboardKPIs:
    service = DashboardService(db)
    return await service.get_kpis(current_user)
