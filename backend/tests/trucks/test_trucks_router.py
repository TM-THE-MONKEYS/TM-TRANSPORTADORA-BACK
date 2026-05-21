"""Tests for truck endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_truck(
    client: AsyncClient, operador_headers: dict[str, str], operador_user: object
) -> None:
    response = await client.post(
        "/api/v1/trucks",
        json={
            "placa": "ABC1234",
            "modelo": "FH 540",
            "marca": "Volvo",
            "ano": 2022,
            "capacidade_kg": 25000.0,
            "consumo_km_l": 2.5,
        },
        headers=operador_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["plate"] == "ABC1234"
    assert data["status"] == "disponivel"


@pytest.mark.asyncio
async def test_create_truck_duplicate_placa(
    client: AsyncClient, operador_headers: dict[str, str], operador_user: object
) -> None:
    payload = {
        "placa": "XYZ5678",
        "modelo": "Actros",
        "marca": "Mercedes",
        "ano": 2021,
        "capacidade_kg": 20000.0,
    }
    first = await client.post("/api/v1/trucks", json=payload, headers=operador_headers)
    assert first.status_code == 201

    second = await client.post("/api/v1/trucks", json=payload, headers=operador_headers)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_list_trucks(
    client: AsyncClient, admin_headers: dict[str, str], admin_user: object
) -> None:
    response = await client.get("/api/v1/trucks", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data


@pytest.mark.asyncio
async def test_update_truck_status(
    client: AsyncClient, operador_headers: dict[str, str], operador_user: object
) -> None:
    create_resp = await client.post(
        "/api/v1/trucks",
        json={
            "placa": "UPD1111",
            "modelo": "TGX",
            "marca": "MAN",
            "ano": 2020,
            "capacidade_kg": 22000.0,
        },
        headers=operador_headers,
    )
    truck_id = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/api/v1/trucks/{truck_id}",
        json={"status": "em_manutencao"},
        headers=operador_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] in ("em_manutencao", "disponivel")
