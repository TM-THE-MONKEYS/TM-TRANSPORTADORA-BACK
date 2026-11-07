"""Motorista must never receive monetary freight amounts."""
from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.modules.clients.models import Client
from app.modules.drivers.models import Driver
from app.modules.freights.models import Freight, FreightCost
from app.modules.tenants.models import Tenant
from app.modules.users.models import User
from app.shared.enums import CNHCategory, DriverStatus, FreightStatus, UserRole


async def _setup_motorista_freight(
    db_session: AsyncSession, tenant: Tenant
) -> tuple[Freight, User, Driver]:
    client = Client(
        nome="Cliente Redact",
        cpf_cnpj="11222333000181",
        is_active=True,
        tenant_id=tenant.id,
    )
    db_session.add(client)
    await db_session.flush()

    user = User(
        nome="Motorista Redact",
        email="motorista.redact@test.com",
        hashed_password=hash_password("Motorista@123!"),
        role=UserRole.MOTORISTA,
        is_active=True,
        tenant_id=tenant.id,
    )
    db_session.add(user)
    await db_session.flush()

    driver = Driver(
        user_id=user.id,
        nome="MOTORISTA REDACT",
        cpf="39053344705",
        cnh="12345678901",
        cnh_category=CNHCategory.C,
        cnh_expiry=date(2030, 12, 31),
        status=DriverStatus.ATIVO,
        tenant_id=tenant.id,
    )
    db_session.add(driver)
    await db_session.flush()

    freight = Freight(
        client_id=client.id,
        driver_id=driver.id,
        origem={"cidade": "CURITIBA", "estado": "PR"},
        destino={"cidade": "LONDRINA", "estado": "PR"},
        valor_frete=9876.54,
        status=FreightStatus.EM_TRANSPORTE,
        tenant_id=tenant.id,
    )
    db_session.add(freight)
    await db_session.flush()

    cost = FreightCost(
        freight_id=freight.id,
        tipo="pedagio",
        valor=120.0,
        descricao="PEDAGIO",
        tenant_id=tenant.id,
    )
    db_session.add(cost)
    await db_session.commit()
    await db_session.refresh(freight)
    await db_session.refresh(user)
    return freight, user, driver


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.role, tenant_id=user.tenant_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_motorista_list_and_detail_hide_value(
    client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    freight, user, _ = await _setup_motorista_freight(db_session, test_tenant)
    headers = _headers(user)

    listed = await client.get("/api/v1/freights", headers=headers)
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == str(freight.id)
    assert items[0]["value_brl"] is None

    detail = await client.get(f"/api/v1/freights/{freight.id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["value_brl"] is None
    assert body["origin_city"] == "CURITIBA"


@pytest.mark.asyncio
async def test_motorista_summary_forbidden(
    client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    _, user, _ = await _setup_motorista_freight(db_session, test_tenant)
    response = await client.get("/api/v1/freights/summary", headers=_headers(user))
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_motorista_costs_redacted(
    client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    freight, user, _ = await _setup_motorista_freight(db_session, test_tenant)
    headers = _headers(user)

    costs = await client.get(f"/api/v1/freights/{freight.id}/costs", headers=headers)
    assert costs.status_code == 200
    rows = costs.json()
    assert len(rows) >= 1
    assert all(row.get("valor") is None for row in rows)

    summary = await client.get(
        f"/api/v1/freights/costs-summary?ids={freight.id}",
        headers=headers,
    )
    assert summary.status_code == 200
    items = summary.json()
    assert len(items) == 1
    assert items[0]["total_costs"] is None


@pytest.mark.asyncio
async def test_motorista_tracking_detail_hides_money(
    client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    freight, user, _ = await _setup_motorista_freight(db_session, test_tenant)
    response = await client.get(
        f"/api/v1/tracking/{freight.id}/detail",
        headers=_headers(user),
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["freight"]["value_brl"] is None
    assert data["fuel_total_valor"] is None
