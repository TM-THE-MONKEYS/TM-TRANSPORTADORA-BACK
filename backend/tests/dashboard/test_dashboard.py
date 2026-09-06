"""Tests for dashboard endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tenants.models import Tenant


@pytest.mark.asyncio
async def test_dashboard_kpis(
    client: AsyncClient, admin_headers: dict[str, str], admin_user: object
) -> None:
    response = await client.get("/api/v1/dashboard/kpis", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "freights_in_progress" in data
    assert "active_trucks" in data
    assert "available_drivers" in data
    assert "monthly_revenue_brl" in data
    assert "maintenance_alerts" in data


@pytest.mark.asyncio
async def test_dashboard_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/dashboard/kpis")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_motorista_forbidden(
    client: AsyncClient, db_session: object, test_tenant: object
) -> None:
    import uuid

    from app.core.security.jwt import create_access_token
    from app.core.security.password import hash_password
    from app.modules.users.models import User
    from app.shared.enums import UserRole

    session = db_session  # type: ignore[assignment]
    motorista = User(
        nome="Motorista Test",
        email=f"motor_{uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("Motor@123!"),
        role=UserRole.MOTORISTA,
        is_active=True,
        tenant_id=test_tenant.id,  # type: ignore[attr-defined]
    )
    session.add(motorista)  # type: ignore[union-attr]
    await session.commit()  # type: ignore[union-attr]
    await session.refresh(motorista)  # type: ignore[union-attr]

    token = create_access_token(motorista.id, motorista.role, tenant_id=motorista.tenant_id)
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/api/v1/dashboard/kpis", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_dashboard_kpis_filter_by_client_and_truck(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    from tests.freights.test_freights_router import _create_freight

    truck_a = await client.post(
        "/api/v1/trucks",
        json={
                "placa": "DASHAA1",
            "modelo": "FH 540",
            "marca": "Volvo",
            "ano": 2022,
            "capacidade_kg": 25000.0,
        },
        headers=admin_headers,
    )
    truck_b = await client.post(
        "/api/v1/trucks",
        json={
                "placa": "DASHBB2",
            "modelo": "R450",
            "marca": "Scania",
            "ano": 2021,
            "capacidade_kg": 28000.0,
        },
        headers=admin_headers,
    )
    assert truck_a.status_code == 201, truck_a.text
    assert truck_b.status_code == 201, truck_b.text
    truck_a_id = truck_a.json()["id"]
    truck_b_id = truck_b.json()["id"]

    freight_a = await _create_freight(
        client,
        admin_headers,
        db_session,
        test_tenant,
        valor=1000.0,
        truck_id=truck_a_id,
    )
    freight_b = await _create_freight(
        client,
        admin_headers,
        db_session,
        test_tenant,
        valor=2500.0,
        truck_id=truck_b_id,
    )

    get_a = await client.get(f"/api/v1/freights/{freight_a}", headers=admin_headers)
    get_b = await client.get(f"/api/v1/freights/{freight_b}", headers=admin_headers)
    assert get_a.status_code == 200
    assert get_b.status_code == 200
    client_a_id = get_a.json()["customer_id"]

    unfiltered = await client.get("/api/v1/dashboard/kpis", headers=admin_headers)
    assert unfiltered.status_code == 200
    base = unfiltered.json()
    assert base["freights_in_progress"] >= 2
    assert base["monthly_revenue_brl"] >= 3500.0

    by_client = await client.get(
        f"/api/v1/dashboard/kpis?client_id={client_a_id}",
        headers=admin_headers,
    )
    assert by_client.status_code == 200
    client_data = by_client.json()
    assert client_data["freights_in_progress"] == 1
    assert client_data["monthly_revenue_brl"] == 1000.0
    assert client_data["freights_in_progress"] < base["freights_in_progress"]
    assert client_data["monthly_revenue_brl"] < base["monthly_revenue_brl"]

    by_truck = await client.get(
        f"/api/v1/dashboard/kpis?truck_id={truck_b_id}",
        headers=admin_headers,
    )
    assert by_truck.status_code == 200
    truck_data = by_truck.json()
    assert truck_data["freights_in_progress"] == 1
    assert truck_data["monthly_revenue_brl"] == 2500.0


@pytest.mark.asyncio
async def test_dashboard_kpis_rejects_competencia_too_far_ahead(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    from datetime import date

    today = date.today()
    total = today.year * 12 + (today.month - 1) + 3
    year, month = total // 12, total % 12 + 1
    response = await client.get(
        f"/api/v1/dashboard/kpis?competencia_mes={month}&competencia_ano={year}",
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "2 meses à frente" in response.json()["detail"]
