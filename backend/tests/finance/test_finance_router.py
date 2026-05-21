"""Tests for finance endpoints."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.modules.users.models import User
from app.shared.enums import UserRole


async def _make_financeiro_user(db_session: AsyncSession) -> tuple[User, str]:
    user = User(
        nome="Financeiro Test",
        email=f"financeiro_{uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("Fin@123!"),
        role=UserRole.FINANCEIRO,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token = create_access_token(user.id, user.role)
    return user, token


@pytest.mark.asyncio
async def test_finance_requires_financeiro_or_admin(
    client: AsyncClient, operador_headers: dict[str, str], operador_user: object
) -> None:
    response = await client.get("/api/v1/finance", headers=operador_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_finance_entry(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, token = await _make_financeiro_user(db_session)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/v1/finance",
        json={
            "tipo": "receita",
            "categoria": "Frete",
            "descricao": "Frete SP-RJ",
            "valor": 2500.00,
        },
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["tipo"] == "receita"
    assert data["valor"] == 2500.00


@pytest.mark.asyncio
async def test_cash_flow(client: AsyncClient, db_session: AsyncSession) -> None:
    _, token = await _make_financeiro_user(db_session)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/finance/cash-flow", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_receitas" in data
    assert "total_despesas" in data
    assert "saldo" in data
