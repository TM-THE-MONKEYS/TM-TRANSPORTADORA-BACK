"""Tests for freight intermediate stops."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client


async def _create_client(db_session: AsyncSession, test_tenant: object) -> Client:
    client_row = Client(
        nome="Cliente Stops",
        cpf_cnpj="39053344705",
        is_active=True,
        tenant_id=test_tenant.id,  # type: ignore[attr-defined]
    )
    db_session.add(client_row)
    await db_session.commit()
    await db_session.refresh(client_row)
    return client_row


@pytest.mark.asyncio
async def test_create_freight_with_stops_returns_ordered_stops(
    client: AsyncClient,
    operador_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: object,
) -> None:
    client_row = await _create_client(db_session, test_tenant)

    response = await client.post(
        "/api/v1/freights",
        json={
            "client_id": str(client_row.id),
            "origem": {
                "logradouro": "Rua X",
                "cidade": "Ribeirão Preto",
                "estado": "SP",
                "cep": "14000-000",
            },
            "destino": {
                "logradouro": "Porto",
                "cidade": "Santos",
                "estado": "SP",
                "cep": "11000-000",
            },
            "paradas": [
                {
                    "ordem": 1,
                    "logradouro": "Rod. Anhanguera, km 102",
                    "cidade": "Campinas",
                    "estado": "SP",
                    "observacoes": "Soja — lote 1",
                },
                {
                    "ordem": 2,
                    "logradouro": "Av. Brasil",
                    "cidade": "Sorocaba",
                    "estado": "SP",
                },
            ],
            "valor_frete": 18500.00,
            "observacoes": "Soja em grãos",
        },
        headers=operador_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert len(data["stops"]) == 2
    assert data["stops"][0]["sequence"] == 1
    assert data["stops"][0]["city"] == "CAMPINAS"
    assert data["stops"][0]["cargo_description"] == "Soja — lote 1"
    assert data["stops"][1]["sequence"] == 2
    assert data["origin_city"] == "RIBEIRÃO PRETO"
    assert data["destination_city"] == "SANTOS"

    freight_id = data["id"]
    get_resp = await client.get(f"/api/v1/freights/{freight_id}", headers=operador_headers)
    assert get_resp.status_code == 200
    assert len(get_resp.json()["stops"]) == 2

    list_resp = await client.get("/api/v1/freights", headers=operador_headers)
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    found = next(i for i in items if i["id"] == freight_id)
    assert len(found["stops"]) == 2


@pytest.mark.asyncio
async def test_create_freight_without_stops_unchanged(
    client: AsyncClient,
    operador_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: object,
) -> None:
    client_row = await _create_client(db_session, test_tenant)

    response = await client.post(
        "/api/v1/freights",
        json={
            "client_id": str(client_row.id),
            "origem": {"logradouro": "Rua A", "cidade": "São Paulo", "estado": "SP"},
            "destino": {"logradouro": "Rua B", "cidade": "Rio de Janeiro", "estado": "RJ"},
            "valor_frete": 1500.00,
        },
        headers=operador_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["stops"] == []


@pytest.mark.asyncio
async def test_create_freight_invalid_stop_order(
    client: AsyncClient,
    operador_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: object,
) -> None:
    client_row = await _create_client(db_session, test_tenant)

    response = await client.post(
        "/api/v1/freights",
        json={
            "client_id": str(client_row.id),
            "origem": {"logradouro": "Rua A", "cidade": "São Paulo", "estado": "SP"},
            "destino": {"logradouro": "Rua B", "cidade": "Rio de Janeiro", "estado": "RJ"},
            "paradas": [{"ordem": 2, "cidade": "Campinas", "estado": "SP"}],
            "valor_frete": 1500.00,
        },
        headers=operador_headers,
    )
    assert response.status_code == 422
