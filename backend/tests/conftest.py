"""Pytest configuration and shared fixtures."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database.base import Base

import app.modules.fuel.models  # noqa: F401
import app.modules.notifications.models  # noqa: F401 — registra tabelas no metadata
import app.modules.tolls.models  # noqa: F401
from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.main import create_app
from app.modules.tenants.models import Tenant
from app.modules.users.models import User
from app.shared.enums import UserRole

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncGenerator[Any, None]:
    eng = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(autouse=True)
async def reset_db(engine: Any) -> AsyncGenerator[None, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def db_session(engine: Any) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def app(db_session: AsyncSession) -> FastAPI:
    from app.api.v1.dependencies.database import get_db

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    application = create_app()
    application.dependency_overrides[get_db] = _override_get_db
    return application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def test_tenant(db_session: AsyncSession) -> Tenant:
    tenant = Tenant(nome="Tenant Test", documento="12345678000199")
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession, test_tenant: Tenant) -> User:
    user = User(
        nome="Admin Test",
        email="admin@test.com",
        hashed_password=hash_password("Admin@123!"),
        role=UserRole.ADMIN,
        is_active=True,
        tenant_id=test_tenant.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def operador_user(db_session: AsyncSession, test_tenant: Tenant) -> User:
    user = User(
        nome="Operador Test",
        email="operador@test.com",
        hashed_password=hash_password("Operador@123!"),
        role=UserRole.OPERADOR,
        is_active=True,
        tenant_id=test_tenant.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
def admin_token(admin_user: User) -> str:
    return create_access_token(admin_user.id, admin_user.role, tenant_id=admin_user.tenant_id)


@pytest_asyncio.fixture
def operador_token(operador_user: User) -> str:
    return create_access_token(
        operador_user.id, operador_user.role, tenant_id=operador_user.tenant_id
    )


@pytest_asyncio.fixture
def admin_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest_asyncio.fixture
def operador_headers(operador_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {operador_token}"}


@pytest_asyncio.fixture
async def motorista_user(db_session: AsyncSession, test_tenant: Tenant) -> User:
    user = User(
        nome="Motorista Test",
        email="motorista@test.com",
        hashed_password=hash_password("Motorista@123!"),
        role=UserRole.MOTORISTA,
        is_active=True,
        tenant_id=test_tenant.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
def motorista_token(motorista_user: User) -> str:
    return create_access_token(
        motorista_user.id, motorista_user.role, tenant_id=motorista_user.tenant_id
    )


@pytest_asyncio.fixture
def motorista_headers(motorista_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {motorista_token}"}
