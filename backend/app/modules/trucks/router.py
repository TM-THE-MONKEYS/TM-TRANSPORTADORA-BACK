"""Truck routes."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_active_user
from app.api.v1.dependencies.database import get_db
from app.modules.trucks.schemas import (
    TruckCreate,
    TruckListResponse,
    TruckRead,
    TruckUpdate,
)
from app.modules.trucks.service import TruckService
from app.modules.users.models import User
from app.shared.enums import TruckStatus
from app.shared.pagination import PagedResponse, PageParams

router = APIRouter(prefix="/trucks", tags=["trucks"])


@router.get("", response_model=PagedResponse[TruckListResponse])
async def list_trucks(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    status: TruckStatus | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
) -> PagedResponse[TruckListResponse]:
    service = TruckService(db)
    params = PageParams(page=page, size=size)
    return await service.list(params, status, search)  # type: ignore[return-value]


@router.post("", response_model=TruckRead, status_code=status.HTTP_201_CREATED)
async def create_truck(
    payload: TruckCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TruckRead:
    service = TruckService(db)
    return await service.create(payload, current_user)  # type: ignore[return-value]


@router.get("/{truck_id}", response_model=TruckRead)
async def get_truck(
    truck_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TruckRead:
    service = TruckService(db)
    return await service.get_by_id(truck_id)  # type: ignore[return-value]


@router.patch("/{truck_id}", response_model=TruckRead)
async def update_truck(
    truck_id: uuid.UUID,
    payload: TruckUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TruckRead:
    service = TruckService(db)
    return await service.update(truck_id, payload, current_user)  # type: ignore[return-value]


@router.delete("/{truck_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_truck(
    truck_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    service = TruckService(db)
    await service.delete(truck_id, current_user)
