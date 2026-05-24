"""Client routes."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from starlette.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_active_user
from app.api.v1.dependencies.database import get_db
from app.modules.clients.schemas import (
    ClientCreate,
    ClientListResponse,
    ClientRead,
    ClientUpdate,
)
from app.modules.clients.service import ClientService
from app.modules.users.models import User
from app.shared.pagination import PagedResponse, PageParams

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=PagedResponse[ClientListResponse])
async def list_clients(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
) -> PagedResponse[ClientListResponse]:
    service = ClientService(db)
    params = PageParams(page=page, size=size)
    return await service.list(params, current_user, is_active, search)  # type: ignore[return-value]


@router.post("", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: ClientCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ClientRead:
    service = ClientService(db)
    return await service.create(payload, current_user)  # type: ignore[return-value]


@router.get("/{client_id}", response_model=ClientRead)
async def get_client(
    client_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ClientRead:
    service = ClientService(db)
    return await service.get_by_id(client_id, current_user)  # type: ignore[return-value]


@router.patch("/{client_id}", response_model=ClientRead)
async def update_client(
    client_id: uuid.UUID,
    payload: ClientUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ClientRead:
    service = ClientService(db)
    return await service.update(client_id, payload, current_user)  # type: ignore[return-value]


@router.delete(
    "/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_client(
    client_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Response:
    service = ClientService(db)
    await service.delete(client_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
