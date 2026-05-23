"""Tests for tracking endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client
from app.modules.freights.models import Freight
from app.shared.enums import FreightStatus


async def _create_freight(db_session: AsyncSession) -> Freight:
    client = Client(
        nome="Cliente Rastreamento",
        cpf_cnpj="52998224725",
        is_active=True,
    )
    db_session.add(client)
    await db_session.flush()

    freight = Freight(
        client_id=client.id,
        origem={"cidade": "São Paulo", "estado": "SP", "logradouro": "Rua A"},
        destino={"cidade": "Rio de Janeiro", "estado": "RJ", "logradouro": "Rua B"},
        valor_frete=1500.0,
        status=FreightStatus.EM_TRANSPORTE,
    )
    db_session.add(freight)
    await db_session.commit()
    await db_session.refresh(freight)
    return freight


@pytest.mark.asyncio
async def test_add_tracking_update(
    client: AsyncClient,
    operador_headers: dict[str, str],
    operador_user: object,
    db_session: AsyncSession,
) -> None:
    freight = await _create_freight(db_session)

    response = await client.post(
        "/api/v1/tracking",
        json={
            "freight_id": str(freight.id),
            "status": "em_transito",
            "descricao": "Saiu de São Paulo",
            "cidade": "São Paulo",
            "estado": "SP",
        },
        headers=operador_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "em_transito"
    assert data.get("notification_id") is not None


@pytest.mark.asyncio
async def test_get_tracking_timeline(
    client: AsyncClient,
    operador_headers: dict[str, str],
    operador_user: object,
    db_session: AsyncSession,
) -> None:
    freight = await _create_freight(db_session)

    # Add two tracking updates
    for status, city in [("coletado", "SP"), ("em_transito", "CWB")]:
        await client.post(
            "/api/v1/tracking",
            json={
                "freight_id": str(freight.id),
                "status": status,
                "cidade": city,
                "estado": "SP" if city == "SP" else "PR",
            },
            headers=operador_headers,
        )

    timeline_resp = await client.get(
        f"/api/v1/tracking/{freight.id}/timeline",
        headers=operador_headers,
    )
    assert timeline_resp.status_code == 200
    data = timeline_resp.json()
    assert data["freight_id"] == str(freight.id)
    assert len(data["updates"]) == 2
    assert data["current_status"] == "em_transito"


@pytest.mark.asyncio
async def test_get_empty_timeline(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: object,
    db_session: AsyncSession,
) -> None:
    freight = await _create_freight(db_session)
    response = await client.get(
        f"/api/v1/tracking/{freight.id}/timeline",
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["updates"] == []
    assert data["current_status"] is None
