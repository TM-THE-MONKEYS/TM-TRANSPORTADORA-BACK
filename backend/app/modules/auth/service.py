"""Auth service: login, logout, refresh, password reset."""
from __future__ import annotations

import uuid

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
from app.modules.auth.schemas import (
    AuthUserResponse,
    LoginResponse,
    TokenResponse,
    permissions_for_role,
    role_to_frontend,
)
from app.modules.drivers.repository import DriverRepository
from app.modules.tenants.models import Tenant
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.shared.enums import UserRole
from app.shared.exceptions.custom import (
    BadRequestException,
    ConflictException,
    UnauthorizedException,
)

log = structlog.get_logger(__name__)
settings = get_settings()


def _build_user_response(user: User) -> AuthUserResponse:
    return AuthUserResponse(
        id=user.id,
        email=user.email,
        name=user.nome,
        role=role_to_frontend(user.role),
        tenant_id=str(user.tenant_id),
        branch_id=None,
        permissions=permissions_for_role(user.role),
    )


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _make_token_response(self, access_token: str, raw_refresh: str) -> TokenResponse:
        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    def _repos_for(self, tenant_id: uuid.UUID) -> tuple[UserRepository, RefreshTokenRepository, DriverRepository]:
        return (
            UserRepository(self._session, tenant_id),
            RefreshTokenRepository(self._session, tenant_id),
            DriverRepository(self._session, tenant_id),
        )

    async def _issue_tokens(
        self, user: User, device_info: str | None = None
    ) -> LoginResponse:
        access_token = create_access_token(user.id, user.role, tenant_id=user.tenant_id)
        raw_refresh, _ = create_refresh_token()
        _, token_repo, _ = self._repos_for(user.tenant_id)
        await token_repo.create(user.id, raw_refresh, device_info)
        await self._session.commit()
        return LoginResponse(
            tokens=self._make_token_response(access_token, raw_refresh),
            user=_build_user_response(user),
        )

    async def login(
        self, email: str, password: str, device_info: str | None = None
    ) -> LoginResponse:
        from sqlalchemy import select

        result = await self._session.execute(
            select(User).where(User.email == email.lower(), User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedException("Credenciais inválidas")

        if not user.is_active:
            raise UnauthorizedException("Conta desativada")

        if user.role == UserRole.MOTORISTA:
            raise UnauthorizedException(
                "Motoristas devem usar a rota /api/v1/auth/driver/login"
            )

        log.info("user_logged_in", user_id=str(user.id), email=user.email)
        return await self._issue_tokens(user, device_info)

    async def login_driver(
        self, cpf: str, password: str, device_info: str | None = None
    ) -> LoginResponse:
        from sqlalchemy import select

        from app.modules.drivers.models import Driver

        result = await self._session.execute(
            select(Driver).where(Driver.cpf == cpf, Driver.deleted_at.is_(None))
        )
        driver = result.scalar_one_or_none()
        if not driver or not driver.user_id:
            raise UnauthorizedException("Credenciais inválidas")

        user_result = await self._session.execute(
            select(User).where(User.id == driver.user_id, User.deleted_at.is_(None))
        )
        user = user_result.scalar_one_or_none()
        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedException("Credenciais inválidas")

        if not user.is_active:
            raise UnauthorizedException("Conta desativada")

        if user.role != UserRole.MOTORISTA:
            raise UnauthorizedException("Credenciais inválidas")

        log.info("driver_logged_in", user_id=str(user.id), driver_id=str(driver.id))
        return await self._issue_tokens(user, device_info)

    async def get_me(self, user: User) -> AuthUserResponse:
        return _build_user_response(user)

    async def register_tenant(
        self,
        tenant_name: str,
        admin_name: str,
        email: str,
        password: str,
        document: str | None = None,
    ) -> LoginResponse:
        if not settings.allow_tenant_registration:
            raise BadRequestException("Registro de tenant desabilitado")

        from sqlalchemy import select

        existing = await self._session.execute(
            select(User).where(User.email == email.lower(), User.deleted_at.is_(None))
        )
        if existing.scalar_one_or_none():
            raise ConflictException("Email já cadastrado")

        tenant = Tenant(nome=tenant_name, documento=document)
        self._session.add(tenant)
        await self._session.flush()
        await self._session.refresh(tenant)

        hashed = hash_password(password)
        user = User(
            nome=admin_name,
            email=email.lower(),
            hashed_password=hashed,
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=tenant.id,
        )
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)

        log.info("tenant_registered", email=email, tenant_name=tenant_name, tenant_id=str(tenant.id))
        return await self._issue_tokens(user)

    async def refresh(self, raw_token: str) -> LoginResponse:
        from app.core.security.jwt import hash_refresh_token
        from app.modules.auth.models import RefreshToken
        from sqlalchemy import select

        result = await self._session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
        )
        token = result.scalar_one_or_none()
        if not token or not token.is_valid:
            raise UnauthorizedException("Refresh token inválido ou expirado")

        user_result = await self._session.execute(
            select(User).where(User.id == token.user_id, User.deleted_at.is_(None))
        )
        user = user_result.scalar_one_or_none()
        if not user or not user.is_active:
            raise UnauthorizedException("Usuário inativo")

        _, token_repo, _ = self._repos_for(user.tenant_id)
        await token_repo.revoke(token)

        access_token = create_access_token(user.id, user.role, tenant_id=user.tenant_id)
        raw_new, _ = create_refresh_token()
        await token_repo.create(user.id, raw_new, token.device_info)
        await self._session.commit()

        return LoginResponse(
            tokens=self._make_token_response(access_token, raw_new),
            user=_build_user_response(user),
        )

    async def logout(self, raw_token: str) -> None:
        from app.core.security.jwt import hash_refresh_token
        from app.modules.auth.models import RefreshToken
        from sqlalchemy import select

        result = await self._session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
        )
        token = result.scalar_one_or_none()
        if token:
            from datetime import datetime as _dt
            from datetime import timezone as _tz
            token.revoked_at = _dt.now(_tz.utc)
            await self._session.flush()
            await self._session.commit()

    async def logout_all(self, user: User) -> None:
        _, token_repo, _ = self._repos_for(user.tenant_id)
        await token_repo.revoke_all_for_user(user.id)
        await self._session.commit()

    async def forgot_password(self, email: str) -> str | None:
        """Returns reset token if user exists (caller decides how to send)."""
        from sqlalchemy import select

        result = await self._session.execute(
            select(User).where(User.email == email.lower(), User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()
        if not user:
            return None
        return create_password_reset_token(user.id)

    async def reset_password(self, token: str, new_password: str) -> None:
        from uuid import UUID

        from jose import JWTError
        from sqlalchemy import select
        try:
            user_id_str = decode_password_reset_token(token)
            user_id = UUID(user_id_str)
        except (JWTError, ValueError):
            raise BadRequestException("Token inválido ou expirado")

        result = await self._session.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()
        if not user:
            raise BadRequestException("Usuário não encontrado")

        user.hashed_password = hash_password(new_password)
        _, token_repo, _ = self._repos_for(user.tenant_id)
        await token_repo.revoke_all_for_user(user.id)
        await self._session.commit()
        log.info("password_reset", user_id=str(user_id))

    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise BadRequestException("Senha atual incorreta")
        user.hashed_password = hash_password(new_password)
        _, token_repo, _ = self._repos_for(user.tenant_id)
        await token_repo.revoke_all_for_user(user.id)
        await self._session.commit()
