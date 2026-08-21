"""Strict freight status transitions + admin reopen."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client
from app.modules.tenants.models import Tenant


async def _create_in_transit_freight(
    client: AsyncClient,
    headers: dict[str, str],
    db_session: AsyncSession,
    tenant: Tenant,
) -> str:
    db_client = Client(
        nome="Cliente Status",
        cpf_cnpj=f"{uuid.uuid4().int % 10**14:014d}",
        tenant_id=tenant.id,
    )
    db_session.add(db_client)
    await db_session.commit()
    await db_session.refresh(db_client)

    response = await client.post(
        "/api/v1/freights",
        json={
            "client_id": str(db_client.id),
            "origem": {"logradouro": "Rua A", "cidade": "São Paulo", "estado": "SP"},
            "destino": {"logradouro": "Rua B", "cidade": "Rio de Janeiro", "estado": "RJ"},
            "valor_frete": 1800.0,
            "status": "em_transporte",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.mark.asyncio
async def test_operador_cannot_reopen_entregue(
    client: AsyncClient,
    operador_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    freight_id = await _create_in_transit_freight(
        client, operador_headers, db_session, test_tenant
    )
    adv = await client.post(
        f"/api/v1/freights/{freight_id}/advance-status",
        headers=operador_headers,
    )
    assert adv.status_code == 200
    assert adv.json()["status"] == "entregue"

    reopen = await client.patch(
        f"/api/v1/freights/{freight_id}/status",
        json={"status": "em_transporte"},
        headers=operador_headers,
    )
    assert reopen.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_reopen_entregue(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    freight_id = await _create_in_transit_freight(
        client, admin_headers, db_session, test_tenant
    )
    await client.post(
        f"/api/v1/freights/{freight_id}/advance-status",
        headers=admin_headers,
    )
    reopen = await client.patch(
        f"/api/v1/freights/{freight_id}/status",
        json={"status": "em_transporte"},
        headers=admin_headers,
    )
    assert reopen.status_code == 200, reopen.text
    assert reopen.json()["status"] == "em_transporte"


@pytest.mark.asyncio
async def test_cannot_jump_entregue_to_cancelado(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    freight_id = await _create_in_transit_freight(
        client, admin_headers, db_session, test_tenant
    )
    await client.post(
        f"/api/v1/freights/{freight_id}/advance-status",
        headers=admin_headers,
    )
    bad = await client.patch(
        f"/api/v1/freights/{freight_id}/status",
        json={"status": "cancelado"},
        headers=admin_headers,
    )
    assert bad.status_code == 403


@pytest.mark.asyncio
async def test_em_transporte_can_cancel(
    client: AsyncClient,
    operador_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    freight_id = await _create_in_transit_freight(
        client, operador_headers, db_session, test_tenant
    )
    resp = await client.patch(
        f"/api/v1/freights/{freight_id}/status",
        json={"status": "cancelado"},
        headers=operador_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelado"
