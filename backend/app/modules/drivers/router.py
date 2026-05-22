"""Driver routes."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from starlette.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_active_user
from app.api.v1.dependencies.database import get_db
from app.modules.drivers.schemas import (
    DriverCreate,
    DriverFrontendListItem,
    DriverFrontendRead,
    DriverUpdate,
)
from app.modules.drivers.service import DriverService
from app.modules.users.models import User
from app.shared.enums import DriverStatus
from app.shared.pagination import PagedResponse, PageParams

router = APIRouter(prefix="/drivers", tags=["drivers"])


@router.get("", response_model=PagedResponse[DriverFrontendListItem])
async def list_drivers(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    status: DriverStatus | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
) -> PagedResponse[DriverFrontendListItem]:
    service = DriverService(db)
    params = PageParams(page=page, size=size)
    result = await service.list(params, status, search)
    frontend_items = [DriverFrontendListItem.from_orm(d) for d in result.items]
    return PagedResponse.create(frontend_items, result.total, params)


@router.post("", response_model=DriverFrontendRead, status_code=status.HTTP_201_CREATED)
async def create_driver(
    payload: DriverCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> DriverFrontendRead:
    service = DriverService(db)
    driver = await service.create(payload, current_user)
    return DriverFrontendRead.from_orm(driver)


@router.get("/{driver_id}", response_model=DriverFrontendRead)
async def get_driver(
    driver_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> DriverFrontendRead:
    service = DriverService(db)
    driver = await service.get_by_id(driver_id)
    return DriverFrontendRead.from_orm(driver)


@router.patch("/{driver_id}", response_model=DriverFrontendRead)
async def update_driver(
    driver_id: uuid.UUID,
    payload: DriverUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> DriverFrontendRead:
    service = DriverService(db)
    driver = await service.update(driver_id, payload, current_user)
    return DriverFrontendRead.from_orm(driver)


@router.delete(
    "/{driver_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_driver(
    driver_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Response:
    service = DriverService(db)
    await service.delete(driver_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
