"""Seed script to populate the database with initial data."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.database.engine import get_engine
from app.core.database.session import AsyncSessionLocal
from app.core.security.password import hash_password
import app.modules.auth.models  # noqa: F401 — registra RefreshToken para o mapper User
from app.modules.users.models import User
from app.shared.enums import UserRole

log = structlog.get_logger()
settings = get_settings()


async def seed_admin_user(session: AsyncSession) -> None:
    from sqlalchemy import select

    # Produção: nunca cria nem altera usuário. A conta admin do cliente permanece intacta.
    if settings.app_env == "production":
        log.info("seed_admin_skipped", reason="production")
        return

    email = settings.seed_admin_email.strip()
    password = settings.seed_admin_password
    if not email or not password:
        log.info(
            "seed_admin_skipped",
            reason="defina SEED_ADMIN_EMAIL e SEED_ADMIN_PASSWORD só no ambiente local",
        )
        return

    result = await session.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()
    if existing:
        # Usuário já existe: não mexe em senha, role nem dados.
        log.info("admin_user_exists")
        return

    admin = User(
        nome="Administrador",
        email=email,
        hashed_password=hash_password(password),
        role=UserRole.ADMIN,
        is_active=True,
    )
    session.add(admin)
    await session.commit()
    log.info("admin_user_created")


async def main() -> None:
    log.info("seed_started")
    async with AsyncSessionLocal() as session:
        await seed_admin_user(session)
    log.info("seed_completed")


if __name__ == "__main__":
    asyncio.run(main())
