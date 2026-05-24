"""Testes de autorização anti-IDOR (motorista não acessa dados de terceiros)."""
from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.modules.clients.models import Client
from app.modules.drivers.models import Driver
from app.modules.freights.models import Freight
from app.modules.users.models import User
from app.shared.enums import CNHCategory, DriverStatus, FreightStatus, UserRole


async def _setup_two_drivers_freight(
    db_session: AsyncSession,
) -> tuple[Freight, User, User, Driver]:
    client = Client(nome="Cliente Sec", cpf_cnpj="11222333000181", is_active=True)
    db_session.add(client)
    await db_session.flush()

    owner_user = User(
        nome="Motorista Dono",
        email="dono.frete@test.com",
        hashed_password=hash_password("Motorista@123!"),
        role=UserRole.MOTORISTA,
        is_active=True,
    )
    intruder_user = User(
        nome="Motorista Intruso",
        email="intruso.frete@test.com",
        hashed_password=hash_password("Motorista@123!"),
        role=UserRole.MOTORISTA,
        is_active=True,
    )
    db_session.add_all([owner_user, intruder_user])
    await db_session.flush()

    owner_driver = Driver(
        user_id=owner_user.id,
        nome="DONO",
        cpf="39053344705",
        cnh="12345678901",
        cnh_category=CNHCategory.C,
        cnh_expiry=date(2030, 12, 31),
        status=DriverStatus.ATIVO,
    )
    intruder_driver = Driver(
        user_id=intruder_user.id,
        nome="INTRUSO",
        cpf="52998224725",
        cnh="98765432109",
        cnh_category=CNHCategory.C,
        cnh_expiry=date(2030, 12, 31),
        status=DriverStatus.ATIVO,
    )
    db_session.add_all([owner_driver, intruder_driver])
    await db_session.flush()

    owner_freight = Freight(
        client_id=client.id,
        driver_id=owner_driver.id,
        origem={"cidade": "CURITIBA", "estado": "PR"},
        destino={"cidade": "FLORIANÓPOLIS", "estado": "SC"},
        valor_frete=5000.0,
        status=FreightStatus.EM_TRANSPORTE,
    )
    intruder_freight = Freight(
        client_id=client.id,
        driver_id=intruder_driver.id,
        origem={"cidade": "SÃO PAULO", "estado": "SP"},
        destino={"cidade": "RIO", "estado": "RJ"},
        valor_frete=3000.0,
        status=FreightStatus.EM_TRANSPORTE,
    )
    db_session.add_all([owner_freight, intruder_freight])
    await db_session.commit()
    await db_session.refresh(owner_freight)
    await db_session.refresh(intruder_user)
    return owner_freight, owner_user, intruder_user, intruder_driver


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_motorista_cannot_get_other_freight(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    freight, _, intruder, _ = await _setup_two_drivers_freight(db_session)

    response = await client.get(
        f"/api/v1/freights/{freight.id}",
        headers=_headers(intruder),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_motorista_cannot_get_other_freight_timeline(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    freight, _, intruder, _ = await _setup_two_drivers_freight(db_session)

    response = await client.get(
        f"/api/v1/tracking/{freight.id}/timeline",
        headers=_headers(intruder),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_motorista_cannot_list_clients(
    client: AsyncClient,
    motorista_headers: dict[str, str],
) -> None:
    response = await client.get("/api/v1/clients", headers=motorista_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_motorista_cannot_list_drivers(
    client: AsyncClient,
    motorista_headers: dict[str, str],
) -> None:
    response = await client.get("/api/v1/drivers", headers=motorista_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_motorista_list_freights_only_own(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_freight, _, intruder, intruder_driver = await _setup_two_drivers_freight(db_session)

    response = await client.get("/api/v1/freights", headers=_headers(intruder))
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert str(owner_freight.id) not in ids

    result = await db_session.execute(
        select(Freight.id).where(Freight.driver_id == intruder_driver.id)
    )
    intruder_freight_id = result.scalar_one()
    assert str(intruder_freight_id) in ids


@pytest.mark.asyncio
async def test_motorista_cannot_spoof_driver_id_filter(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    freight, _, intruder, owner_driver = await _setup_two_drivers_freight(db_session)

    response = await client.get(
        f"/api/v1/freights?driver_id={owner_driver.id}",
        headers=_headers(intruder),
    )
    assert response.status_code == 403
