"""Truck routes."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from starlette.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_active_user
from app.api.v1.dependencies.database import get_db
from app.modules.trucks.implement_schemas import (
    TruckImplementCreate,
    TruckImplementFrontendRead,
    TruckImplementUpdate,
)
from app.modules.trucks.implement_service import TruckImplementService
from app.modules.trucks.schemas import (
    TruckCreate,
    TruckFrontendListItem,
    TruckFrontendRead,
    TruckUpdate,
)
from app.modules.trucks.service import TruckService
from app.modules.users.models import User
from app.shared.enums import TruckStatus
from app.shared.pagination import PagedResponse, PageParams

router = APIRouter(prefix="/trucks", tags=["trucks"])


@router.get("", response_model=PagedResponse[TruckFrontendListItem])
async def list_trucks(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    status: TruckStatus | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
) -> PagedResponse[TruckFrontendListItem]:
    service = TruckService(db, current_user.tenant_id)
    params = PageParams(page=page, size=size)
    result = await service.list(params, current_user, status, search)
    frontend_items = [TruckFrontendListItem.from_orm(t) for t in result.items]
    return PagedResponse.create(frontend_items, result.total, params)


@router.post("", response_model=TruckFrontendRead, status_code=status.HTTP_201_CREATED)
async def create_truck(
    payload: TruckCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TruckFrontendRead:
    service = TruckService(db, current_user.tenant_id)
    truck = await service.create(payload, current_user)
    return TruckFrontendRead.from_orm(truck)


@router.get("/{truck_id}", response_model=TruckFrontendRead)
async def get_truck(
    truck_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TruckFrontendRead:
    service = TruckService(db, current_user.tenant_id)
    truck = await service.get_by_id(truck_id, current_user)
    return TruckFrontendRead.from_orm(truck)


@router.patch("/{truck_id}", response_model=TruckFrontendRead)
async def update_truck(
    truck_id: uuid.UUID,
    payload: TruckUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TruckFrontendRead:
    service = TruckService(db, current_user.tenant_id)
    truck = await service.update(truck_id, payload, current_user)
    return TruckFrontendRead.from_orm(truck)


@router.delete(
    "/{truck_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_truck(
    truck_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Response:
    service = TruckService(db, current_user.tenant_id)
    await service.delete(truck_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{truck_id}/implements", response_model=list[TruckImplementFrontendRead])
async def list_truck_implements(
    truck_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[TruckImplementFrontendRead]:
    service = TruckImplementService(db, current_user.tenant_id)
    items = await service.list(truck_id, current_user)
    return [TruckImplementFrontendRead.from_orm(item) for item in items]


@router.post(
    "/{truck_id}/implements",
    response_model=TruckImplementFrontendRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_truck_implement(
    truck_id: uuid.UUID,
    payload: TruckImplementCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TruckImplementFrontendRead:
    service = TruckImplementService(db, current_user.tenant_id)
    implement = await service.create(truck_id, payload, current_user)
    return TruckImplementFrontendRead.from_orm(implement)


@router.patch(
    "/{truck_id}/implements/{implement_id}",
    response_model=TruckImplementFrontendRead,
)
async def update_truck_implement(
    truck_id: uuid.UUID,
    implement_id: uuid.UUID,
    payload: TruckImplementUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TruckImplementFrontendRead:
    service = TruckImplementService(db, current_user.tenant_id)
    implement = await service.update(truck_id, implement_id, payload, current_user)
    return TruckImplementFrontendRead.from_orm(implement)


@router.delete(
    "/{truck_id}/implements/{implement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_truck_implement(
    truck_id: uuid.UUID,
    implement_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Response:
    service = TruckImplementService(db, current_user.tenant_id)
    await service.delete(truck_id, implement_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
