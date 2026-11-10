"""Tests for freight start-trip (KM inicial) and odometer-end."""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.modules.clients.models import Client
from app.modules.drivers.models import Driver
from app.modules.freights.models import Freight
from app.modules.tenants.models import Tenant
from app.modules.trucks.models import Truck
from app.modules.users.models import User
from app.shared.enums import (
    CNHCategory,
    DriverStatus,
    FreightStatus,
    TruckStatus,
    UserRole,
)

_START_PAYLOAD = {
    "km_inicial": 1500.0,
    "check_docs": True,
    "check_veiculo": True,
    "check_carga": True,
}


async def _seed_trip_context(
    db_session: AsyncSession,
    tenant: Tenant,
    *,
    truck_km: float = 1000.0,
    link_motorista: bool = True,
) -> tuple[Freight, Truck, User, Driver, User]:
    """Returns freight, truck, motorista_user, driver, other_motorista_user."""
    client = Client(
        nome="Cliente Trip",
        cpf_cnpj=f"{uuid.uuid4().int % 10**14:014d}",
        tenant_id=tenant.id,
    )
    truck = Truck(
        placa=f"TRP{uuid.uuid4().hex[:4].upper()}",
        modelo="FH",
        marca="Volvo",
        ano=2022,
        capacidade_kg=20000,
        km_atual=truck_km,
        status=TruckStatus.DISPONIVEL,
        tenant_id=tenant.id,
    )
    motorista = User(
        nome="Motorista Trip",
        email=f"motorista.trip.{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hash_password("Motorista@123!"),
        role=UserRole.MOTORISTA,
        is_active=True,
        tenant_id=tenant.id,
    )
    other = User(
        nome="Outro Motorista",
        email=f"outro.trip.{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hash_password("Motorista@123!"),
        role=UserRole.MOTORISTA,
        is_active=True,
        tenant_id=tenant.id,
    )
    db_session.add_all([client, truck, motorista, other])
    await db_session.flush()

    driver = Driver(
        user_id=motorista.id if link_motorista else None,
        nome="MOTORISTA TRIP",
        cpf=f"{uuid.uuid4().int % 10**11:011d}",
        cnh=f"{uuid.uuid4().int % 10**11:011d}",
        cnh_category=CNHCategory.C,
        cnh_expiry=date(2030, 12, 31),
        status=DriverStatus.ATIVO,
        tenant_id=tenant.id,
    )
    other_driver = Driver(
        user_id=other.id,
        nome="OUTRO MOTORISTA",
        cpf=f"{uuid.uuid4().int % 10**11:011d}",
        cnh=f"{uuid.uuid4().int % 10**11:011d}",
        cnh_category=CNHCategory.C,
        cnh_expiry=date(2030, 12, 31),
        status=DriverStatus.ATIVO,
        tenant_id=tenant.id,
    )
    db_session.add_all([driver, other_driver])
    await db_session.flush()

    freight = Freight(
        client_id=client.id,
        driver_id=driver.id,
        truck_id=truck.id,
        origem={"logradouro": "Rua A", "cidade": "São Paulo", "estado": "SP"},
        destino={"logradouro": "Rua B", "cidade": "Rio de Janeiro", "estado": "RJ"},
        valor_frete=2500.0,
        status=FreightStatus.EM_TRANSPORTE,
        tenant_id=tenant.id,
    )
    db_session.add(freight)
    await db_session.commit()
    await db_session.refresh(freight)
    await db_session.refresh(truck)
    await db_session.refresh(motorista)
    await db_session.refresh(driver)
    await db_session.refresh(other)
    return freight, truck, motorista, driver, other


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.role, tenant_id=user.tenant_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_start_trip_success_as_motorista(
    client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    freight, truck, motorista, _, _ = await _seed_trip_context(db_session, test_tenant)
    headers = _auth_headers(motorista)

    response = await client.post(
        f"/api/v1/freights/{freight.id}/start-trip",
        json=_START_PAYLOAD,
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["km_inicial"] == 1500.0
    assert body["check_docs"] is True
    assert body["check_veiculo"] is True
    assert body["check_carga"] is True
    assert body["km_inicial_registrado_em"] is not None
    assert body["value_brl"] is None  # motorista redaction

    truck_id = truck.id
    db_session.expire_all()
    refreshed_truck = await db_session.get(Truck, truck_id)
    assert refreshed_truck is not None
    assert refreshed_truck.status == TruckStatus.EM_VIAGEM
    assert refreshed_truck.km_atual == 1500.0


@pytest.mark.asyncio
async def test_start_trip_forbidden_other_motorista(
    client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    freight, _, _, _, other = await _seed_trip_context(db_session, test_tenant)

    response = await client.post(
        f"/api/v1/freights/{freight.id}/start-trip",
        json=_START_PAYLOAD,
        headers=_auth_headers(other),
    )
    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_start_trip_km_below_truck_fails(
    client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    freight, _, motorista, _, _ = await _seed_trip_context(
        db_session, test_tenant, truck_km=2000.0
    )

    response = await client.post(
        f"/api/v1/freights/{freight.id}/start-trip",
        json={
            "km_inicial": 1500.0,
            "check_docs": True,
            "check_veiculo": True,
            "check_carga": True,
        },
        headers=_auth_headers(motorista),
    )
    assert response.status_code == 400, response.text


@pytest.mark.asyncio
async def test_truck_becomes_em_viagem_only_after_start(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    freight, truck, motorista, _, _ = await _seed_trip_context(db_session, test_tenant)
    truck_id = truck.id
    freight_id = freight.id
    tenant_id = test_tenant.id
    motorista_headers = _auth_headers(motorista)

    assert truck.status == TruckStatus.DISPONIVEL

    # Create via API also must not flip truck until start-trip
    client_row = Client(
        nome="Cliente Create",
        cpf_cnpj=f"{uuid.uuid4().int % 10**14:014d}",
        tenant_id=tenant_id,
    )
    db_session.add(client_row)
    await db_session.commit()
    await db_session.refresh(client_row)
    client_id = client_row.id

    create = await client.post(
        "/api/v1/freights",
        json={
            "client_id": str(client_id),
            "truck_id": str(truck_id),
            "origem": {"logradouro": "Rua A", "cidade": "São Paulo", "estado": "SP"},
            "destino": {"logradouro": "Rua B", "cidade": "Campinas", "estado": "SP"},
            "valor_frete": 1000.0,
            "status": "em_transporte",
        },
        headers=admin_headers,
    )
    assert create.status_code == 201, create.text

    db_session.expire_all()
    after_create = await db_session.get(Truck, truck_id)
    assert after_create is not None
    assert after_create.status == TruckStatus.DISPONIVEL

    start = await client.post(
        f"/api/v1/freights/{freight_id}/start-trip",
        json=_START_PAYLOAD,
        headers=motorista_headers,
    )
    assert start.status_code == 200, start.text

    db_session.expire_all()
    after_start = await db_session.get(Truck, truck_id)
    assert after_start is not None
    assert after_start.status == TruckStatus.EM_VIAGEM


@pytest.mark.asyncio
async def test_admin_can_start_trip(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    freight, truck, _, _, _ = await _seed_trip_context(db_session, test_tenant)
    truck_id = truck.id
    freight_id = freight.id

    response = await client.post(
        f"/api/v1/freights/{freight_id}/start-trip",
        json=_START_PAYLOAD,
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["km_inicial"] == 1500.0
    assert body["value_brl"] == 2500.0

    # Regression: list uses load_only; km_inicial must be selected or async raises 503.
    list_resp = await client.get("/api/v1/freights", headers=admin_headers)
    assert list_resp.status_code == 200, list_resp.text
    listed = next(i for i in list_resp.json()["items"] if i["id"] == str(freight_id))
    assert listed["km_inicial"] == 1500.0

    db_session.expire_all()
    refreshed = await db_session.get(Truck, truck_id)
    assert refreshed is not None
    assert refreshed.status == TruckStatus.EM_VIAGEM


@pytest.mark.asyncio
async def test_start_trip_conflict_when_already_started(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    freight, _, _, _, _ = await _seed_trip_context(db_session, test_tenant)

    first = await client.post(
        f"/api/v1/freights/{freight.id}/start-trip",
        json=_START_PAYLOAD,
        headers=admin_headers,
    )
    assert first.status_code == 200, first.text

    second = await client.post(
        f"/api/v1/freights/{freight.id}/start-trip",
        json=_START_PAYLOAD,
        headers=admin_headers,
    )
    assert second.status_code == 409, second.text


@pytest.mark.asyncio
async def test_odometer_end_success(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    freight, truck, _, _, _ = await _seed_trip_context(db_session, test_tenant)
    truck_id = truck.id
    freight_id = freight.id

    start = await client.post(
        f"/api/v1/freights/{freight_id}/start-trip",
        json=_START_PAYLOAD,
        headers=admin_headers,
    )
    assert start.status_code == 200, start.text

    end = await client.post(
        f"/api/v1/freights/{freight_id}/odometer-end",
        json={"km_final": 1800.0},
        headers=admin_headers,
    )
    assert end.status_code == 200, end.text
    body = end.json()
    assert body["km_final"] == 1800.0
    assert body["km_final_registrado_em"] is not None

    db_session.expire_all()
    refreshed = await db_session.get(Truck, truck_id)
    assert refreshed is not None
    assert refreshed.km_atual == 1800.0


@pytest.mark.asyncio
async def test_odometer_end_requires_km_inicial(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    freight, _, _, _, _ = await _seed_trip_context(db_session, test_tenant)

    response = await client.post(
        f"/api/v1/freights/{freight.id}/odometer-end",
        json={"km_final": 1800.0},
        headers=admin_headers,
    )
    assert response.status_code == 400, response.text


@pytest.mark.asyncio
async def test_start_trip_checks_required(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    freight, _, _, _, _ = await _seed_trip_context(db_session, test_tenant)

    response = await client.post(
        f"/api/v1/freights/{freight.id}/start-trip",
        json={
            "km_inicial": 1500.0,
            "check_docs": True,
            "check_veiculo": False,
            "check_carga": True,
        },
        headers=admin_headers,
    )
    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_motorista_advance_to_entregue_requires_km_final(
    client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    freight, _, motorista, _, _ = await _seed_trip_context(db_session, test_tenant)
    token = create_access_token(
        motorista.id, motorista.role, tenant_id=motorista.tenant_id
    )
    headers = {"Authorization": f"Bearer {token}"}

    start = await client.post(
        f"/api/v1/freights/{freight.id}/start-trip",
        json=_START_PAYLOAD,
        headers=headers,
    )
    assert start.status_code == 200, start.text

    blocked = await client.post(
        f"/api/v1/freights/{freight.id}/advance-status",
        headers=headers,
    )
    assert blocked.status_code == 400, blocked.text

    end = await client.post(
        f"/api/v1/freights/{freight.id}/odometer-end",
        json={"km_final": 1800.0},
        headers=headers,
    )
    assert end.status_code == 200, end.text

    delivered = await client.post(
        f"/api/v1/freights/{freight.id}/advance-status",
        headers=headers,
    )
    assert delivered.status_code == 200, delivered.text
    assert delivered.json()["status"] == "entregue"
