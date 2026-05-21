"""Tests for maintenance endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.trucks.models import Truck


async def _create_truck(db_session: AsyncSession) -> Truck:
    truck = Truck(
        placa=f"MNT{uuid.uuid4().hex[:4].upper()}",
        modelo="FH 460",
        marca="Volvo",
        ano=2021,
        capacidade_kg=20000.0,
    )
    db_session.add(truck)
    await db_session.commit()
    await db_session.refresh(truck)
    return truck


@pytest.mark.asyncio
async def test_create_maintenance(
    client: AsyncClient,
    operador_headers: dict[str, str],
    operador_user: object,
    db_session: AsyncSession,
) -> None:
    truck = await _create_truck(db_session)
    response = await client.post(
        "/api/v1/maintenance",
        json={
            "truck_id": str(truck.id),
            "tipo": "preventiva",
            "descricao": "Troca de óleo e filtros",
            "custo": 850.00,
            "status": "agendada",
            "data_prevista": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        },
        headers=operador_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["tipo"] == "preventiva"
    assert data["custo"] == 850.00


@pytest.mark.asyncio
async def test_list_maintenance(
    client: AsyncClient, admin_headers: dict[str, str], admin_user: object
) -> None:
    response = await client.get("/api/v1/maintenance", headers=admin_headers)
    assert response.status_code == 200
    assert "items" in response.json()


@pytest.mark.asyncio
async def test_maintenance_alerts(
    client: AsyncClient,
    operador_headers: dict[str, str],
    operador_user: object,
    db_session: AsyncSession,
) -> None:
    truck = await _create_truck(db_session)
    await client.post(
        "/api/v1/maintenance",
        json={
            "truck_id": str(truck.id),
            "tipo": "corretiva",
            "descricao": "Revisão de freios urgente",
            "status": "agendada",
            "data_prevista": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
        },
        headers=operador_headers,
    )

    alerts_resp = await client.get(
        "/api/v1/maintenance/alerts?days_ahead=30",
        headers=operador_headers,
    )
    assert alerts_resp.status_code == 200
    assert isinstance(alerts_resp.json(), list)


@pytest.mark.asyncio
async def test_get_maintenance_not_found(
    client: AsyncClient, admin_headers: dict[str, str], admin_user: object
) -> None:
    response = await client.get(
        f"/api/v1/maintenance/{uuid.uuid4()}",
        headers=admin_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_maintenance_status(
    client: AsyncClient,
    operador_headers: dict[str, str],
    operador_user: object,
    db_session: AsyncSession,
) -> None:
    truck = await _create_truck(db_session)
    create_resp = await client.post(
        "/api/v1/maintenance",
        json={
            "truck_id": str(truck.id),
            "tipo": "preventiva",
            "descricao": "Alinhamento e balanceamento",
            "status": "agendada",
        },
        headers=operador_headers,
    )
    maintenance_id = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/api/v1/maintenance/{maintenance_id}",
        json={"status": "em_andamento"},
        headers=operador_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "em_andamento"


@pytest.mark.asyncio
async def test_delete_maintenance(
    client: AsyncClient,
    operador_headers: dict[str, str],
    operador_user: object,
    db_session: AsyncSession,
) -> None:
    truck = await _create_truck(db_session)
    create_resp = await client.post(
        "/api/v1/maintenance",
        json={
            "truck_id": str(truck.id),
            "tipo": "corretiva",
            "descricao": "Reparo no motor",
            "status": "agendada",
        },
        headers=operador_headers,
    )
    maintenance_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/v1/maintenance/{maintenance_id}",
        headers=operador_headers,
    )
    assert del_resp.status_code == 204
