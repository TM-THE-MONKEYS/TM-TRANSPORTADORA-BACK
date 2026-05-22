"""Freight routes."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from starlette.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_active_user
from app.api.v1.dependencies.database import get_db
from app.modules.freights.schemas import (
    FreightCostCreate,
    FreightCostRead,
    FreightCreate,
    FreightFrontendListItem,
    FreightFrontendRead,
    FreightStatusUpdate,
    FreightUpdate,
)
from app.modules.freights.service import FreightService
from app.modules.users.models import User
from app.shared.enums import FreightStatus
from app.shared.pagination import PagedResponse, PageParams

router = APIRouter(prefix="/freights", tags=["freights"])


@router.get("", response_model=PagedResponse[FreightFrontendListItem])
async def list_freights(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    status: FreightStatus | None = Query(default=None),
    client_id: uuid.UUID | None = Query(default=None),
    driver_id: uuid.UUID | None = Query(default=None),
    truck_id: uuid.UUID | None = Query(default=None),
) -> PagedResponse[FreightFrontendListItem]:
    service = FreightService(db)
    params = PageParams(page=page, size=size)
    result = await service.list(params, status, client_id, driver_id, truck_id)
    frontend_items = [FreightFrontendListItem.from_orm(f) for f in result.items]
    return PagedResponse.create(frontend_items, result.total, params)


@router.post("", response_model=FreightFrontendRead, status_code=status.HTTP_201_CREATED)
async def create_freight(
    payload: FreightCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> FreightFrontendRead:
    service = FreightService(db)
    freight = await service.create(payload, current_user)
    return FreightFrontendRead.from_orm(freight)


@router.get("/{freight_id}", response_model=FreightFrontendRead)
async def get_freight(
    freight_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> FreightFrontendRead:
    service = FreightService(db)
    freight = await service.get_by_id(freight_id)
    return FreightFrontendRead.from_orm(freight)


@router.patch("/{freight_id}", response_model=FreightFrontendRead)
async def update_freight(
    freight_id: uuid.UUID,
    payload: FreightUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> FreightFrontendRead:
    service = FreightService(db)
    freight = await service.update(freight_id, payload, current_user)
    return FreightFrontendRead.from_orm(freight)


@router.post("/{freight_id}/advance-status", response_model=FreightFrontendRead)
async def advance_freight_status(
    freight_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> FreightFrontendRead:
    service = FreightService(db)
    freight = await service.advance_status(freight_id, current_user)
    return FreightFrontendRead.from_orm(freight)


@router.patch("/{freight_id}/status", response_model=FreightFrontendRead)
async def update_freight_status(
    freight_id: uuid.UUID,
    payload: FreightStatusUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> FreightFrontendRead:
    service = FreightService(db)
    freight = await service.update_status(freight_id, payload.status, current_user)
    return FreightFrontendRead.from_orm(freight)


@router.delete(
    "/{freight_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_freight(
    freight_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Response:
    service = FreightService(db)
    await service.delete(freight_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{freight_id}/costs", response_model=FreightCostRead, status_code=status.HTTP_201_CREATED)
async def add_freight_cost(
    freight_id: uuid.UUID,
    payload: FreightCostCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> FreightCostRead:
    service = FreightService(db)
    return await service.add_cost(freight_id, payload, current_user)  # type: ignore[return-value]
