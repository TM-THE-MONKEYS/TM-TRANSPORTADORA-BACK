"""Freight mutations must sync truck disponivel ↔ em_viagem on the backend."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client
from app.modules.tenants.models import Tenant
from app.modules.trucks.models import Truck
from app.shared.enums import TruckStatus


async def _seed_client_and_truck(
    db_session: AsyncSession, tenant: Tenant
) -> tuple[Client, Truck]:
    client = Client(
        nome="Cliente Sync",
        cpf_cnpj=f"{uuid.uuid4().int % 10**14:014d}",
        tenant_id=tenant.id,
    )
    truck = Truck(
        placa=f"SYN{uuid.uuid4().hex[:4].upper()}",
        modelo="FH",
        marca="Volvo",
        ano=2022,
        capacidade_kg=20000,
        km_atual=1000,
        status=TruckStatus.DISPONIVEL,
        tenant_id=tenant.id,
    )
    db_session.add_all([client, truck])
    await db_session.commit()
    await db_session.refresh(client)
    await db_session.refresh(truck)
    return client, truck


@pytest.mark.asyncio
async def test_create_freight_sets_truck_em_viagem(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    db_client, truck = await _seed_client_and_truck(db_session, test_tenant)
    truck_id = truck.id

    response = await client.post(
        "/api/v1/freights",
        json={
            "client_id": str(db_client.id),
            "truck_id": str(truck_id),
            "origem": {"logradouro": "Rua A", "cidade": "São Paulo", "estado": "SP"},
            "destino": {"logradouro": "Rua B", "cidade": "Rio de Janeiro", "estado": "RJ"},
            "valor_frete": 2000.0,
            "status": "em_transporte",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text

    db_session.expire_all()
    refreshed = await db_session.get(Truck, truck_id)
    assert refreshed is not None
    assert refreshed.status == TruckStatus.EM_VIAGEM


@pytest.mark.asyncio
async def test_advance_to_entregue_releases_truck(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    db_client, truck = await _seed_client_and_truck(db_session, test_tenant)
    truck_id = truck.id

    create = await client.post(
        "/api/v1/freights",
        json={
            "client_id": str(db_client.id),
            "truck_id": str(truck_id),
            "origem": {"logradouro": "Rua A", "cidade": "São Paulo", "estado": "SP"},
            "destino": {"logradouro": "Rua B", "cidade": "Rio de Janeiro", "estado": "RJ"},
            "valor_frete": 2000.0,
            "status": "em_transporte",
        },
        headers=admin_headers,
    )
    assert create.status_code == 201, create.text
    freight_id = create.json()["id"]

    advance = await client.post(
        f"/api/v1/freights/{freight_id}/advance-status",
        headers=admin_headers,
    )
    assert advance.status_code == 200, advance.text
    assert advance.json()["status"] == "entregue"

    db_session.expire_all()
    refreshed = await db_session.get(Truck, truck_id)
    assert refreshed is not None
    assert refreshed.status == TruckStatus.DISPONIVEL


@pytest.mark.asyncio
async def test_sync_does_not_override_maintenance(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    db_client, truck = await _seed_client_and_truck(db_session, test_tenant)
    truck_id = truck.id
    truck.status = TruckStatus.EM_MANUTENCAO
    await db_session.commit()

    response = await client.post(
        "/api/v1/freights",
        json={
            "client_id": str(db_client.id),
            "truck_id": str(truck_id),
            "origem": {"logradouro": "Rua A", "cidade": "São Paulo", "estado": "SP"},
            "destino": {"logradouro": "Rua B", "cidade": "Rio de Janeiro", "estado": "RJ"},
            "valor_frete": 2000.0,
            "status": "em_transporte",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text

    db_session.expire_all()
    refreshed = await db_session.get(Truck, truck_id)
    assert refreshed is not None
    assert refreshed.status == TruckStatus.EM_MANUTENCAO
