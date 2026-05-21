"""Auth service: login, logout, refresh, password reset."""
from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.security.jwt import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_password_reset_token,
)
from app.core.security.password import hash_password, verify_password
from app.modules.auth.repository import RefreshTokenRepository
from app.modules.auth.schemas import TokenResponse
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.shared.exceptions.custom import (
    BadRequestException,
    UnauthorizedException,
)

log = structlog.get_logger(__name__)
settings = get_settings()


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._user_repo = UserRepository(session)
        self._token_repo = RefreshTokenRepository(session)

    async def login(
        self, email: str, password: str, device_info: str | None = None
    ) -> TokenResponse:
        user = await self._user_repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedException("Credenciais inválidas")

        if not user.is_active:
            raise UnauthorizedException("Conta desativada")

        access_token = create_access_token(user.id, user.role)
        raw_refresh, _ = create_refresh_token()
        await self._token_repo.create(user.id, raw_refresh, device_info)
        await self._session.commit()

        log.info("user_logged_in", user_id=str(user.id), email=user.email)
        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    async def refresh(self, raw_token: str) -> TokenResponse:
        token = await self._token_repo.get_by_hash(raw_token)
        if not token or not token.is_valid:
            raise UnauthorizedException("Refresh token inválido ou expirado")

        user = await self._user_repo.get_by_id(token.user_id)
        if not user or not user.is_active:
            raise UnauthorizedException("Usuário inativo")

        await self._token_repo.revoke(token)

        access_token = create_access_token(user.id, user.role)
        raw_new, _ = create_refresh_token()
        await self._token_repo.create(user.id, raw_new, token.device_info)
        await self._session.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_new,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    async def logout(self, raw_token: str) -> None:
        token = await self._token_repo.get_by_hash(raw_token)
        if token:
            await self._token_repo.revoke(token)
            await self._session.commit()

    async def logout_all(self, user: User) -> None:
        await self._token_repo.revoke_all_for_user(user.id)
        await self._session.commit()

    async def forgot_password(self, email: str) -> str | None:
        """Returns reset token if user exists (caller decides how to send)."""
        user = await self._user_repo.get_by_email(email)
        if not user:
            return None
        return create_password_reset_token(user.id)

    async def reset_password(self, token: str, new_password: str) -> None:
        from uuid import UUID

        from jose import JWTError
        try:
            user_id_str = decode_password_reset_token(token)
            user_id = UUID(user_id_str)
        except (JWTError, ValueError):
            raise BadRequestException("Token inválido ou expirado")

        user = await self._user_repo.get_by_id(user_id)
        if not user:
            raise BadRequestException("Usuário não encontrado")

        user.hashed_password = hash_password(new_password)
        await self._token_repo.revoke_all_for_user(user.id)
        await self._session.commit()
        log.info("password_reset", user_id=str(user_id))

    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise BadRequestException("Senha atual incorreta")
        user.hashed_password = hash_password(new_password)
        await self._token_repo.revoke_all_for_user(user.id)
        await self._session.commit()
