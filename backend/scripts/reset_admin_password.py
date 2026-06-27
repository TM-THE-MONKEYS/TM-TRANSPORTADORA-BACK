"""Reset admin password for local dev."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import app.modules.auth.models  # noqa: F401
import app.modules.tenants.models  # noqa: F401
from sqlalchemy import select

from app.core.database.session import AsyncSessionLocal
from app.core.security.password import hash_password
from app.modules.users.models import User

ADMIN_EMAIL = "admin@tmtransportadora.com.br"
ADMIN_PASSWORD = "Admin@123!"


async def main() -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == ADMIN_EMAIL))
        user = result.scalar_one_or_none()
        if not user:
            print(f"user_not_found:{ADMIN_EMAIL}")
            return
        user.hashed_password = hash_password(ADMIN_PASSWORD)
        await session.commit()
        print(f"password_reset_ok:{ADMIN_EMAIL}")


if __name__ == "__main__":
    asyncio.run(main())
