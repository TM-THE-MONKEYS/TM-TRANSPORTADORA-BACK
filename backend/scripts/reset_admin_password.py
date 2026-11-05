"""Reset admin password for local dev."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import app.modules.auth.models  # noqa: F401
import app.modules.tenants.models  # noqa: F401
from sqlalchemy import select

from app.core.config.settings import get_settings
from app.core.database.session import AsyncSessionLocal
from app.core.security.password import hash_password
from app.modules.users.models import User


async def main() -> None:
    settings = get_settings()
    if settings.app_env == "production":
        print("refused: reset_admin_password não roda em produção")
        raise SystemExit(1)

    email = settings.seed_admin_email.strip()
    password = settings.seed_admin_password
    if not email or not password:
        print("seed_admin_missing: defina SEED_ADMIN_EMAIL e SEED_ADMIN_PASSWORD no ambiente local")
        raise SystemExit(1)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            print("user_not_found")
            raise SystemExit(1)
        user.hashed_password = hash_password(password)
        await session.commit()
        print("password_reset_ok")


if __name__ == "__main__":
    asyncio.run(main())
