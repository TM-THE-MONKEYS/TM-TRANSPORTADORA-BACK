"""Tests for notification endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client
from app.modules.freights.models import Freight
from app.shared.enums import FreightStatus


async def _create_freight(db_session: AsyncSession) -> Freight:
    client = Client(nome="Cliente Notif", cpf_cnpj="39053344705", is_active=True)
    db_session.add(client)
    await db_session.flush()
    freight = Freight(
        client_id=client.id,
        origem={"cidade": "SAO PAULO", "estado": "SP", "logradouro": "RUA A"},
        destino={"cidade": "CURITIBA", "estado": "PR", "logradouro": "RUA B"},
        valor_frete=2000.0,
        status=FreightStatus.EM_TRANSPORTE,
    )
    db_session.add(freight)
    await db_session.commit()
    await db_session.refresh(freight)
    return freight


@pytest.mark.asyncio
async def test_tracking_creates_notification(
    client: AsyncClient,
    operador_headers: dict[str, str],
    admin_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    freight = await _create_freight(db_session)

    create_resp = await client.post(
        "/api/v1/tracking",
        json={
            "freight_id": str(freight.id),
            "status": "em_transito",
            "descricao": "parada para abastecimento",
            "cidade": "registro",
            "estado": "sp",
        },
        headers=operador_headers,
    )
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["notification_id"] is not None

    notif_resp = await client.get(
        "/api/v1/notifications?unread_only=true",
        headers=admin_headers,
    )
    assert notif_resp.status_code == 200
    notif_data = notif_resp.json()
    assert notif_data["unread_count"] >= 1
    assert any(item["freight_id"] == str(freight.id) for item in notif_data["items"])


@pytest.mark.asyncio
async def test_tracking_detail_endpoint(
    client: AsyncClient,
    operador_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    freight = await _create_freight(db_session)
    await client.post(
        "/api/v1/tracking",
        json={
            "freight_id": str(freight.id),
            "status": "coletado",
            "descricao": "carga coletada",
        },
        headers=operador_headers,
    )

    detail_resp = await client.get(
        f"/api/v1/tracking/{freight.id}/detail",
        headers=operador_headers,
    )
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["freight"]["id"] == str(freight.id)
    assert detail["total_occurrences"] == 1
    assert detail["latest_occurrence"] is not None
    assert len(detail["timeline"]) == 1
