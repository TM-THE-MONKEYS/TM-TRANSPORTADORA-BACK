"""Tests for competência report and fixed expense launch status."""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.modules.users.models import User
from app.shared.enums import UserRole


async def _financeiro_headers(db_session: AsyncSession, test_tenant: object) -> dict[str, str]:
    user = User(
        nome="Financeiro Competencia",
        email=f"fincomp_{uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("Fin@123!"),
        role=UserRole.FINANCEIRO,
        is_active=True,
        tenant_id=test_tenant.id,  # type: ignore[attr-defined]
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token = create_access_token(user.id, user.role, tenant_id=user.tenant_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_competencia_report(
    client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: object,
) -> None:
    headers = await _financeiro_headers(db_session, test_tenant)
    today = date.today()

    create = await client.post(
        "/api/v1/finance",
        json={
            "tipo": "despesa",
            "categoria": "Combustível",
            "descricao": "Teste competência",
            "valor": 500.0,
            "data_vencimento": today.isoformat(),
        },
        headers=headers,
    )
    assert create.status_code == 201

    response = await client.get(
        f"/api/v1/finance/competencia-report?competencia_mes={today.month}&competencia_ano={today.year}",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["competencia_mes"] == today.month
    assert data["competencia_ano"] == today.year
    assert "cash_flow" in data
    assert data["cash_flow"]["total_despesas"] >= 500.0
    assert isinstance(data["daily_series"], list)
    assert isinstance(data["expenses_by_category"], list)


@pytest.mark.asyncio
async def test_fixed_expense_launch_status(
    client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: object,
) -> None:
    headers = await _financeiro_headers(db_session, test_tenant)
    today = date.today()

    created = await client.post(
        "/api/v1/finance/fixed-expenses",
        json={
            "nome": "Aluguel teste",
            "categoria": "Aluguel",
            "valor": 1000.0,
            "frequencia": "mensal",
            "dia_vencimento": 10,
            "ativo": True,
        },
        headers=headers,
    )
    assert created.status_code == 201

    status = await client.get(
        f"/api/v1/finance/fixed-expenses/launch-status?competencia_mes={today.month}&competencia_ano={today.year}",
        headers=headers,
    )
    assert status.status_code == 200
    items = status.json()
    assert any(i["nome"] == "Aluguel teste" and not i["launched_this_month"] for i in items)

    launch = await client.post(
        f"/api/v1/finance/fixed-expenses/launch-pending?competencia_mes={today.month}&competencia_ano={today.year}",
        headers=headers,
    )
    assert launch.status_code == 200
    assert launch.json()["launched_count"] >= 1
