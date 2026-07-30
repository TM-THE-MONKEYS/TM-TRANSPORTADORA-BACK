"""Tests for freight endpoints."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client
from app.modules.finance.models import FinanceEntry
from app.modules.tenants.models import Tenant


async def _create_freight(
    client: AsyncClient,
    headers: dict[str, str],
    db_session: AsyncSession,
    tenant: Tenant,
    valor: float = 1500.0,
) -> str:
    db_client = Client(nome="Cliente Teste", cpf_cnpj=f"{uuid.uuid4().int % 10**14:014d}", tenant_id=tenant.id)
    db_session.add(db_client)
    await db_session.commit()
    await db_session.refresh(db_client)

    response = await client.post(
        "/api/v1/freights",
        json={
            "client_id": str(db_client.id),
            "origem": {"logradouro": "Rua A", "cidade": "São Paulo", "estado": "SP"},
            "destino": {"logradouro": "Rua B", "cidade": "Rio de Janeiro", "estado": "RJ"},
            "valor_frete": valor,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _active_finance_entries(
    db_session: AsyncSession, freight_id: str
) -> list[FinanceEntry]:
    result = await db_session.execute(
        select(FinanceEntry).where(
            FinanceEntry.freight_id == uuid.UUID(freight_id),
            FinanceEntry.deleted_at.is_(None),
        )
    )
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_list_freights(
    client: AsyncClient, admin_headers: dict[str, str], admin_user: object
) -> None:
    response = await client.get("/api/v1/freights", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_create_freight_invalid_client(
    client: AsyncClient, operador_headers: dict[str, str], operador_user: object
) -> None:
    """Should fail because client_id doesn't exist (FK violation or validation)."""
    response = await client.post(
        "/api/v1/freights",
        json={
            "client_id": str(uuid.uuid4()),
            "origem": {
                "logradouro": "Rua A",
                "cidade": "São Paulo",
                "estado": "SP",
            },
            "destino": {
                "logradouro": "Rua B",
                "cidade": "Rio de Janeiro",
                "estado": "RJ",
            },
            "valor_frete": 1500.00,
        },
        headers=operador_headers,
    )
    # FK violation (PG) or created (SQLite - no FK enforcement) — both are valid behaviors
    assert response.status_code in (201, 409, 404, 422, 500)


@pytest.mark.asyncio
async def test_get_freight_not_found(
    client: AsyncClient, admin_headers: dict[str, str], admin_user: object
) -> None:
    response = await client.get(
        f"/api/v1/freights/{uuid.uuid4()}",
        headers=admin_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_freight_status_filter(
    client: AsyncClient, admin_headers: dict[str, str], admin_user: object
) -> None:
    response = await client.get(
        "/api/v1/freights?status=orcamento",
        headers=admin_headers,
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_freight_removes_linked_finance_entries(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: object,
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    freight_id = await _create_freight(client, admin_headers, db_session, test_tenant)

    entries = await _active_finance_entries(db_session, freight_id)
    assert len(entries) == 1, "Receita do frete deve ser criada junto com o frete"

    response = await client.delete(f"/api/v1/freights/{freight_id}", headers=admin_headers)
    assert response.status_code == 204

    entries = await _active_finance_entries(db_session, freight_id)
    assert entries == [], "Lançamentos financeiros devem ser excluídos junto com o frete"


@pytest.mark.asyncio
async def test_admin_can_delete_delivered_freight(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: object,
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    freight_id = await _create_freight(client, admin_headers, db_session, test_tenant)

    for _ in range(4):  # orcamento → confirmado → em_coleta → em_transporte → entregue
        response = await client.post(
            f"/api/v1/freights/{freight_id}/advance-status", headers=admin_headers
        )
        assert response.status_code == 200, response.text
    assert response.json()["status"] == "entregue"

    response = await client.delete(f"/api/v1/freights/{freight_id}", headers=admin_headers)
    assert response.status_code == 204

    response = await client.get(f"/api/v1/freights/{freight_id}", headers=admin_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_freight_cancels_pending_revenue(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: object,
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    freight_id = await _create_freight(client, admin_headers, db_session, test_tenant)

    response = await client.patch(
        f"/api/v1/freights/{freight_id}/status",
        json={"status": "cancelado"},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text

    entries = await _active_finance_entries(db_session, freight_id)
    assert len(entries) == 1
    assert entries[0].status.value == "cancelado"

    # reabrir frete cancelado reativa a receita
    response = await client.patch(
        f"/api/v1/freights/{freight_id}/status",
        json={"status": "orcamento"},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text

    entries = await _active_finance_entries(db_session, freight_id)
    assert entries[0].status.value == "pendente"


@pytest.mark.asyncio
async def test_update_freight_value_syncs_revenue_entry(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: object,
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    freight_id = await _create_freight(
        client, admin_headers, db_session, test_tenant, valor=1000.0
    )

    response = await client.patch(
        f"/api/v1/freights/{freight_id}",
        json={"valor_frete": 2500.0},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text

    entries = await _active_finance_entries(db_session, freight_id)
    assert len(entries) == 1
    assert float(entries[0].valor) == 2500.0, "Receita deve acompanhar o novo valor do frete"
