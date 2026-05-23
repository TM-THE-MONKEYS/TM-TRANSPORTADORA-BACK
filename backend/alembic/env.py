from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config.settings import get_settings
from app.core.database.base import Base  # noqa: F401

# Import all models so Alembic can detect them
import app.modules.users.models  # noqa: F401
import app.modules.auth.models  # noqa: F401
import app.modules.drivers.models  # noqa: F401
import app.modules.trucks.models  # noqa: F401
import app.modules.clients.models  # noqa: F401
import app.modules.freights.models  # noqa: F401
import app.modules.maintenance.models  # noqa: F401
import app.modules.finance.models  # noqa: F401
import app.modules.tracking.models  # noqa: F401
import app.modules.notifications.models  # noqa: F401
import app.modules.fuel.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()

# Use URL object directly to avoid configparser % interpolation issues
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

_DB_URL = settings.database_url_async

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=_DB_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    from app.core.database.engine import (
        _pooler_connect_args,
        _pooler_engine_url,
        _uses_transaction_pooler,
    )

    db_url = _pooler_engine_url(_DB_URL) if _uses_transaction_pooler(_DB_URL) else _DB_URL
    connectable = create_async_engine(
        db_url,
        poolclass=pool.NullPool,
        connect_args=_pooler_connect_args() if _uses_transaction_pooler(_DB_URL) else {},
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
