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
from app.modules.users.models import User
from app.shared.enums import UserRole

log = structlog.get_logger()
settings = get_settings()


async def seed_admin_user(session: AsyncSession) -> None:
    from sqlalchemy import select
    result = await session.execute(select(User).where(User.email == "admin@tmtransportadora.com.br"))
    existing = result.scalar_one_or_none()
    if existing:
        log.info("admin_user_exists", email="admin@tmtransportadora.com.br")
        return

    admin = User(
        nome="Administrador",
        email="admin@tmtransportadora.com.br",
        hashed_password=hash_password("Admin@123!"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    session.add(admin)
    await session.commit()
    log.info("admin_user_created", email="admin@tmtransportadora.com.br")


async def main() -> None:
    log.info("seed_started")
    async with AsyncSessionLocal() as session:
        await seed_admin_user(session)
    log.info("seed_completed")


if __name__ == "__main__":
    asyncio.run(main())
