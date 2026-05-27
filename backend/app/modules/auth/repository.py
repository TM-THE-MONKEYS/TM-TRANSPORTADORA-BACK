"""Auth repository: refresh token CRUD."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.security.jwt import hash_refresh_token
from app.modules.auth.models import RefreshToken
from app.shared.base_repository import TenantBaseRepository

log = structlog.get_logger(__name__)
settings = get_settings()


class RefreshTokenRepository(TenantBaseRepository[RefreshToken]):
    model = RefreshToken

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        super().__init__(session, tenant_id)

    async def create(
        self,
        user_id: uuid.UUID,
        raw_token: str,
        device_info: str | None = None,
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id,
            token_hash=hash_refresh_token(raw_token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.refresh_token_expire_days),
            device_info=device_info,
            tenant_id=self._tenant_id,
        )
        self._session.add(token)
        await self._session.flush()
        return token

    async def get_by_hash(self, raw_token: str) -> RefreshToken | None:
        token_hash = hash_refresh_token(raw_token)
        result = await self._session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.tenant_id == self._tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def revoke(self, token: RefreshToken) -> None:
        token.revoked_at = datetime.now(timezone.utc)
        await self._session.flush()

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        await self._session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.tenant_id == self._tenant_id,
            )
            .values(revoked_at=datetime.now(timezone.utc))
        )

    async def delete_expired(self) -> int:
        from sqlalchemy import delete
        result = await self._session.execute(
            delete(RefreshToken).where(
                RefreshToken.expires_at < datetime.now(timezone.utc)
            )
        )
        return result.rowcount or 0
