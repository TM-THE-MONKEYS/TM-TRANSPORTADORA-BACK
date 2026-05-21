"""Auth routes."""
from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_active_user
from app.api.v1.dependencies.database import get_db
from app.modules.auth.schemas import (
    AuthUserResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    RefreshRequest,
    RegisterTenantRequest,
    ResetPasswordRequest,
)
from app.modules.auth.service import AuthService
from app.modules.users.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
log = structlog.get_logger(__name__)


def _get_device_info(request: Request) -> str:
    return request.headers.get("User-Agent", "unknown")[:255]


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(
    payload: LoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponse:
    service = AuthService(db)
    return await service.login(payload.email, payload.password, _get_device_info(request))


@router.post("/register-tenant", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def register_tenant(
    payload: RegisterTenantRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponse:
    service = AuthService(db)
    return await service.register_tenant(
        payload.tenant_name,
        payload.admin_name,
        payload.email,
        payload.password,
    )


@router.get("/me", response_model=AuthUserResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthUserResponse:
    service = AuthService(db)
    return await service.get_me(current_user)


@router.post("/refresh", response_model=LoginResponse)
async def refresh(
    payload: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponse:
    service = AuthService(db)
    return await service.refresh(payload.refresh_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    payload: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    service = AuthService(db)
    await service.logout(payload.refresh_token)
    return MessageResponse(message="Logout realizado com sucesso")


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    service = AuthService(db)
    await service.logout_all(current_user)
    return MessageResponse(message="Todas as sessões encerradas")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    service = AuthService(db)
    await service.forgot_password(payload.email)
    return MessageResponse(
        message="Se o email existir, você receberá instruções de recuperação"
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    payload: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    service = AuthService(db)
    await service.reset_password(payload.token, payload.new_password)
    return MessageResponse(message="Senha redefinida com sucesso")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    service = AuthService(db)
    await service.change_password(
        current_user, payload.current_password, payload.new_password
    )
    return MessageResponse(message="Senha alterada com sucesso")
