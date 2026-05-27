"""User routes."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from starlette.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_active_user, require_roles
from app.api.v1.dependencies.database import get_db
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate, UserListResponse, UserRead, UserUpdate
from app.modules.users.service import UserService
from app.shared.enums import UserRole
from app.shared.pagination import PagedResponse, PageParams

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def get_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserRead:
    return current_user  # type: ignore[return-value]


@router.get(
    "",
    response_model=PagedResponse[UserListResponse],
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    role: UserRole | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
) -> PagedResponse[UserListResponse]:
    service = UserService(db, current_user.tenant_id)
    params = PageParams(page=page, size=size)
    return await service.list(params, role, is_active, search)  # type: ignore[return-value]


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def create_user(
    payload: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserRead:
    service = UserService(db, current_user.tenant_id)
    return await service.create(payload, current_user)  # type: ignore[return-value]


@router.get(
    "/{user_id}",
    response_model=UserRead,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def get_user(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserRead:
    service = UserService(db, current_user.tenant_id)
    return await service.get_by_id(user_id)  # type: ignore[return-value]


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserRead:
    service = UserService(db, current_user.tenant_id)
    return await service.update(user_id, payload, current_user)  # type: ignore[return-value]


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def delete_user(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Response:
    service = UserService(db, current_user.tenant_id)
    await service.delete(user_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
