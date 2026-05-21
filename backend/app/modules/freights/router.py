"""Freight routes."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_active_user
from app.api.v1.dependencies.database import get_db
from app.modules.freights.schemas import (
    FreightCostCreate,
    FreightCostRead,
    FreightCreate,
    FreightListResponse,
    FreightRead,
    FreightUpdate,
)
from app.modules.freights.service import FreightService
from app.modules.users.models import User
from app.shared.enums import FreightStatus
from app.shared.pagination import PagedResponse, PageParams

router = APIRouter(prefix="/freights", tags=["freights"])


@router.get("", response_model=PagedResponse[FreightListResponse])
async def list_freights(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    status: FreightStatus | None = Query(default=None),
    client_id: uuid.UUID | None = Query(default=None),
    driver_id: uuid.UUID | None = Query(default=None),
    truck_id: uuid.UUID | None = Query(default=None),
) -> PagedResponse[FreightListResponse]:
    service = FreightService(db)
    params = PageParams(page=page, size=size)
    return await service.list(params, status, client_id, driver_id, truck_id)  # type: ignore[return-value]


@router.post("", response_model=FreightRead, status_code=status.HTTP_201_CREATED)
async def create_freight(
    payload: FreightCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> FreightRead:
    service = FreightService(db)
    return await service.create(payload, current_user)  # type: ignore[return-value]


@router.get("/{freight_id}", response_model=FreightRead)
async def get_freight(
    freight_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> FreightRead:
    service = FreightService(db)
    return await service.get_by_id(freight_id)  # type: ignore[return-value]


@router.patch("/{freight_id}", response_model=FreightRead)
async def update_freight(
    freight_id: uuid.UUID,
    payload: FreightUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> FreightRead:
    service = FreightService(db)
    return await service.update(freight_id, payload, current_user)  # type: ignore[return-value]


@router.delete("/{freight_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_freight(
    freight_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    service = FreightService(db)
    await service.delete(freight_id, current_user)


@router.post("/{freight_id}/costs", response_model=FreightCostRead, status_code=status.HTTP_201_CREATED)
async def add_freight_cost(
    freight_id: uuid.UUID,
    payload: FreightCostCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> FreightCostRead:
    service = FreightService(db)
    return await service.add_cost(freight_id, payload, current_user)  # type: ignore[return-value]
