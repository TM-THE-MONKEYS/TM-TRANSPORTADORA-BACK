"""Maintenance routes."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from starlette.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_active_user
from app.api.v1.dependencies.database import get_db
from app.modules.maintenance.schemas import (
    MaintenanceCreate,
    MaintenanceListResponse,
    MaintenanceRead,
    MaintenanceUpdate,
)
from app.modules.maintenance.service import MaintenanceService
from app.modules.users.models import User
from app.shared.enums import MaintenanceStatus, MaintenanceType
from app.shared.pagination import PagedResponse, PageParams

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


@router.get("", response_model=PagedResponse[MaintenanceListResponse])
async def list_maintenance(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    truck_id: uuid.UUID | None = Query(default=None),
    status: MaintenanceStatus | None = Query(default=None),
    tipo: MaintenanceType | None = Query(default=None),
) -> PagedResponse[MaintenanceListResponse]:
    service = MaintenanceService(db)
    params = PageParams(page=page, size=size)
    return await service.list(params, truck_id, status, tipo)  # type: ignore[return-value]


@router.get("/alerts", response_model=list[MaintenanceRead])
async def get_maintenance_alerts(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    days_ahead: int = Query(default=30, ge=1, le=365),
) -> list[MaintenanceRead]:
    service = MaintenanceService(db)
    return await service.get_alerts(days_ahead)  # type: ignore[return-value]


@router.post("", response_model=MaintenanceRead, status_code=status.HTTP_201_CREATED)
async def create_maintenance(
    payload: MaintenanceCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> MaintenanceRead:
    service = MaintenanceService(db)
    return await service.create(payload, current_user)  # type: ignore[return-value]


@router.get("/{maintenance_id}", response_model=MaintenanceRead)
async def get_maintenance(
    maintenance_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> MaintenanceRead:
    service = MaintenanceService(db)
    return await service.get_by_id(maintenance_id)  # type: ignore[return-value]


@router.patch("/{maintenance_id}", response_model=MaintenanceRead)
async def update_maintenance(
    maintenance_id: uuid.UUID,
    payload: MaintenanceUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> MaintenanceRead:
    service = MaintenanceService(db)
    return await service.update(maintenance_id, payload, current_user)  # type: ignore[return-value]


@router.delete(
    "/{maintenance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_maintenance(
    maintenance_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Response:
    service = MaintenanceService(db)
    await service.delete(maintenance_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
