"""Tests for fuel refill endpoints."""
from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.password import hash_password
from app.modules.clients.models import Client
from app.modules.drivers.models import Driver
from app.modules.freights.models import Freight
from app.modules.users.models import User
from app.shared.enums import CNHCategory, DriverStatus, FreightStatus, UserRole
from app.core.security.jwt import create_access_token


async def _setup_freight_with_driver(
    db_session: AsyncSession,
) -> tuple[Freight, Driver, User]:
    motorista_user = User(
        nome="Motorista Fuel",
        email="motorista.fuel@test.com",
        hashed_password=hash_password("Motorista@123!"),
        role=UserRole.MOTORISTA,
        is_active=True,
    )
    db_session.add(motorista_user)
    await db_session.flush()

    driver = Driver(
        user_id=motorista_user.id,
        nome="JOÃO MOTORISTA",
        cpf="39053344705",
        cnh="12345678901",
        cnh_category=CNHCategory.C,
        cnh_expiry=date(2030, 12, 31),
        status=DriverStatus.ATIVO,
    )
    db_session.add(driver)
    await db_session.flush()

    client = Client(nome="Cliente Fuel", cpf_cnpj="11222333000181", is_active=True)
    db_session.add(client)
    await db_session.flush()

    freight = Freight(
        client_id=client.id,
        driver_id=driver.id,
        origem={"cidade": "CURITIBA", "estado": "PR", "logradouro": "RUA A"},
        destino={"cidade": "FLORIANÓPOLIS", "estado": "SC", "logradouro": "RUA B"},
        valor_frete=5000.0,
        status=FreightStatus.EM_TRANSPORTE,
    )
    db_session.add(freight)
    await db_session.commit()
    await db_session.refresh(freight)
    await db_session.refresh(driver)
    await db_session.refresh(motorista_user)
    return freight, driver, motorista_user


@pytest.mark.asyncio
async def test_register_fuel_refill_br_decimal(
    client: AsyncClient,
    operador_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    freight, driver, _ = await _setup_freight_with_driver(db_session)

    response = await client.post(
        "/api/v1/fuel",
        json={
            "freight_id": str(freight.id),
            "driver_id": str(driver.id),
            "litros": "150,5",
            "valor_total": "1.200,75",
            "posto": "Posto BR",
            "cidade": "Joinville",
            "estado": "sc",
        },
        headers=operador_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["litros"] == pytest.approx(150.5)
    assert data["valor_total"] == pytest.approx(1200.75)
    assert data["valor_litro"] == pytest.approx(1200.75 / 150.5, rel=1e-3)
    assert data["freight_cost_id"] is not None
    assert data.get("notification_id") is not None
    assert data["estado"] == "SC"


@pytest.mark.asyncio
async def test_active_freight_for_motorista(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    freight, driver, motorista_user = await _setup_freight_with_driver(db_session)
    token = create_access_token(motorista_user.id, motorista_user.role)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/fuel/active-freight", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["freight_id"] == str(freight.id)
    assert data["driver_id"] == str(driver.id)


@pytest.mark.asyncio
async def test_motorista_registers_fuel_without_driver_id(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    freight, _, motorista_user = await _setup_freight_with_driver(db_session)
    token = create_access_token(motorista_user.id, motorista_user.role)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/v1/fuel",
        json={
            "freightId": str(freight.id),
            "liters": 80,
            "value": "640,00",
        },
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["litros"] == 80.0
    assert response.json()["valor_total"] == 640.0


@pytest.mark.asyncio
async def test_eligible_freights_excludes_entregue_for_motorista(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    freight, driver, motorista_user = await _setup_freight_with_driver(db_session)
    freight_entregue = Freight(
        client_id=freight.client_id,
        driver_id=driver.id,
        origem={"cidade": "SÃO PAULO", "estado": "SP"},
        destino={"cidade": "RIO", "estado": "RJ"},
        valor_frete=3000.0,
        status=FreightStatus.ENTREGUE,
    )
    db_session.add(freight_entregue)
    await db_session.commit()

    token = create_access_token(motorista_user.id, motorista_user.role)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/fuel/eligible-freights", headers=headers)
    assert response.status_code == 200
    ids = {item["freight_id"] for item in response.json()}
    assert str(freight.id) in ids
    assert str(freight_entregue.id) not in ids


@pytest.mark.asyncio
async def test_motorista_cannot_fuel_other_drivers_freight(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    freight, _, _ = await _setup_freight_with_driver(db_session)

    other_motorista = User(
        nome="Outro Motorista",
        email="outro.motorista.fuel@test.com",
        hashed_password=hash_password("Motorista@123!"),
        role=UserRole.MOTORISTA,
        is_active=True,
    )
    db_session.add(other_motorista)
    await db_session.flush()

    other_driver = Driver(
        user_id=other_motorista.id,
        nome="OUTRO MOTORISTA",
        cpf="52998224725",
        cnh="98765432109",
        cnh_category=CNHCategory.C,
        cnh_expiry=date(2030, 12, 31),
        status=DriverStatus.ATIVO,
    )
    db_session.add(other_driver)
    await db_session.commit()
    await db_session.refresh(other_motorista)

    token = create_access_token(other_motorista.id, other_motorista.role)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/v1/fuel",
        json={
            "freight_id": str(freight.id),
            "litros": 50,
            "valor_total": "400,00",
        },
        headers=headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_operador_cannot_use_wrong_driver_id_on_fuel(
    client: AsyncClient,
    operador_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    freight, driver, _ = await _setup_freight_with_driver(db_session)

    other_driver = Driver(
        nome="MOTORISTA EXTRA",
        cpf="11144477735",
        cnh="11122233344",
        cnh_category=CNHCategory.C,
        cnh_expiry=date(2030, 12, 31),
        status=DriverStatus.ATIVO,
    )
    db_session.add(other_driver)
    await db_session.commit()
    await db_session.refresh(other_driver)

    response = await client.post(
        "/api/v1/fuel",
        json={
            "freight_id": str(freight.id),
            "driver_id": str(other_driver.id),
            "litros": 50,
            "valor_total": "400,00",
        },
        headers=operador_headers,
    )
    assert response.status_code == 400
