"""Driver routes."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_active_user
from app.api.v1.dependencies.database import get_db
from app.modules.drivers.schemas import (
    DriverCreate,
    DriverListResponse,
    DriverRead,
    DriverUpdate,
)
from app.modules.drivers.service import DriverService
from app.modules.users.models import User
from app.shared.enums import DriverStatus
from app.shared.pagination import PagedResponse, PageParams

router = APIRouter(prefix="/drivers", tags=["drivers"])


@router.get("", response_model=PagedResponse[DriverListResponse])
async def list_drivers(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    status: DriverStatus | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
) -> PagedResponse[DriverListResponse]:
    service = DriverService(db)
    params = PageParams(page=page, size=size)
    return await service.list(params, status, search)  # type: ignore[return-value]


@router.post("", response_model=DriverRead, status_code=status.HTTP_201_CREATED)
async def create_driver(
    payload: DriverCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> DriverRead:
    service = DriverService(db)
    return await service.create(payload, current_user)  # type: ignore[return-value]


@router.get("/{driver_id}", response_model=DriverRead)
async def get_driver(
    driver_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> DriverRead:
    service = DriverService(db)
    return await service.get_by_id(driver_id)  # type: ignore[return-value]


@router.patch("/{driver_id}", response_model=DriverRead)
async def update_driver(
    driver_id: uuid.UUID,
    payload: DriverUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> DriverRead:
    service = DriverService(db)
    return await service.update(driver_id, payload, current_user)  # type: ignore[return-value]


@router.delete("/{driver_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_driver(
    driver_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    service = DriverService(db)
    await service.delete(driver_id, current_user)
