"""Tests for fixed expenses with limited duration."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.modules.finance.models import FixedExpense
from app.modules.users.models import User
from app.shared.enums import FixedExpenseFrequency, UserRole


async def _financeiro_headers(db_session: AsyncSession, test_tenant: object) -> dict[str, str]:
    user = User(
        nome="Financeiro Fixos",
        email="fin.fixos@test.com",
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
async def test_fixed_expense_launch_until_expired(
    client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: object,
) -> None:
    headers = await _financeiro_headers(db_session, test_tenant)

    create_resp = await client.post(
        "/api/v1/finance/fixed-expenses",
        json={
            "nome": "Financiamento caminhão",
            "categoria": "Outros",
            "valor": 3500.00,
            "frequencia": "mensal",
            "dia_vencimento": 10,
            "total_parcelas": 3,
            "parcelas_lancadas": 0,
            "ativo": True,
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    expense_id = create_resp.json()["id"]

    for _ in range(3):
        launch = await client.post(
            f"/api/v1/finance/fixed-expenses/{expense_id}/launch",
            headers=headers,
        )
        assert launch.status_code == 200
        assert launch.json()["tipo"] == "despesa"
        assert launch.json()["status"] == "pendente"
        assert launch.json()["valor"] == 3500.0

    list_resp = await client.get("/api/v1/finance/fixed-expenses", headers=headers)
    item = next(i for i in list_resp.json() if i["id"] == expense_id)
    assert item["parcelas_lancadas"] == 3
    assert item["ativo"] is False

    fourth = await client.post(
        f"/api/v1/finance/fixed-expenses/{expense_id}/launch",
        headers=headers,
    )
    assert fourth.status_code == 422


@pytest.mark.asyncio
async def test_fixed_expense_expired_by_months_on_list(
    db_session: AsyncSession,
    test_tenant: object,
) -> None:
    start = date.today().replace(day=1) - timedelta(days=365)
    expense = FixedExpense(
        nome="Aluguel antigo",
        categoria="Outros",
        valor=2000.0,
        frequencia=FixedExpenseFrequency.MENSAL,
        total_parcelas=12,
        parcelas_lancadas=0,
        data_inicio=start,
        ativo=True,
        tenant_id=test_tenant.id,  # type: ignore[attr-defined]
    )
    db_session.add(expense)
    await db_session.commit()

    from app.modules.finance.fixed_expense_utils import refresh_expiry

    await db_session.refresh(expense)
    assert refresh_expiry(expense) is True
    assert expense.ativo is False
