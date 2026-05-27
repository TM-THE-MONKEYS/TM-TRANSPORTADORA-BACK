"""Authentication and authorization dependencies."""
from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.database import get_db
from app.core.security.jwt import decode_access_token
from app.modules.users.models import User
from app.shared.enums import UserRole
from app.shared.exceptions.custom import ForbiddenException, UnauthorizedException

log = structlog.get_logger(__name__)
_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    from uuid import UUID

    if not credentials:
        raise UnauthorizedException("Token de autenticação não fornecido")

    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        raise UnauthorizedException("Token inválido ou expirado")

    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise UnauthorizedException("Token inválido")

    try:
        user_id = UUID(sub)
    except ValueError:
        raise UnauthorizedException("Token inválido")

    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise UnauthorizedException("Usuário não encontrado")

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_active:
        raise UnauthorizedException("Conta desativada")
    return current_user


def require_roles(*roles: UserRole):  # type: ignore[no-untyped-def]
    """Dependency factory that requires one of the specified roles."""

    async def _check_role(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        if current_user.role not in roles:
            raise ForbiddenException(
                f"Acesso negado. Role necessária: {', '.join(r.value for r in roles)}"
            )
        return current_user

    return _check_role
