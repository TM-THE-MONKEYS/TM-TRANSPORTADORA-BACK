"""Tests for dashboard endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


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
    client: AsyncClient, db_session: object
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
    )
    session.add(motorista)  # type: ignore[union-attr]
    await session.commit()  # type: ignore[union-attr]
    await session.refresh(motorista)  # type: ignore[union-attr]

    token = create_access_token(motorista.id, motorista.role)
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/api/v1/dashboard/kpis", headers=headers)
    assert response.status_code == 403
