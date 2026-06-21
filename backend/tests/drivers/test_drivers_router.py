"""Tests for driver endpoints."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client
from app.modules.freights.models import Freight
from app.modules.tenants.models import Tenant
from app.shared.enums import FreightStatus


def _future_date() -> str:
    return (date.today() + timedelta(days=365)).isoformat()


@pytest.mark.asyncio
async def test_create_driver_without_password_creates_account(
    client: AsyncClient, operador_headers: dict[str, str], operador_user: object
) -> None:
    cpf = "15350946056"
    response = await client.post(
        "/api/v1/drivers",
        json={
            "nome": "João Motorista",
            "cpf": cpf,
            "cnh": "12345678901",
            "cnh_category": "E",
            "cnh_expiry": _future_date(),
        },
        headers=operador_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "JOÃO MOTORISTA"
    assert data["temporary_password"] is not None

    login_resp = await client.post(
        "/api/v1/auth/driver/login",
        json={"cpf": cpf, "password": data["temporary_password"]},
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["user"]["role"] == "motorista"


@pytest.mark.asyncio
async def test_create_driver(
    client: AsyncClient, operador_headers: dict[str, str], operador_user: object
) -> None:
    response = await client.post(
        "/api/v1/drivers",
        json={
            "nome": "João Motorista",
            "cpf": "52998224725",
            "cnh": "12345678901",
            "cnh_category": "E",
            "cnh_expiry": _future_date(),
        },
        headers=operador_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "JOÃO MOTORISTA"
    assert data["cnh_category"] == "E"


@pytest.mark.asyncio
async def test_create_driver_with_frontend_aliases(
    client: AsyncClient, operador_headers: dict[str, str], operador_user: object
) -> None:
    response = await client.post(
        "/api/v1/drivers",
        json={
            "name": "Maria Motorista",
            "cpf": "39053344705",
            "cnh_number": "98765432109",
            "cnh_category": "D",
            "cnh_expires_at": _future_date(),
            "phone": "11988887777",
        },
        headers=operador_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "MARIA MOTORISTA"
    assert data["phone"] == "11988887777"


@pytest.mark.asyncio
async def test_create_driver_null_cpf_returns_clear_error(
    client: AsyncClient, operador_headers: dict[str, str], operador_user: object
) -> None:
    response = await client.post(
        "/api/v1/drivers",
        json={
            "name": "Sem CPF",
            "cpf": None,
            "cnh_number": "12345678901",
            "cnh_category": "E",
            "cnh_expires_at": _future_date(),
        },
        headers=operador_headers,
    )
    assert response.status_code == 422
    detail = str(response.json()["detail"])
    assert "CPF" in detail


@pytest.mark.asyncio
async def test_create_driver_invalid_cpf(
    client: AsyncClient, operador_headers: dict[str, str], operador_user: object
) -> None:
    response = await client.post(
        "/api/v1/drivers",
        json={
            "nome": "CPF Inválido",
            "cpf": "00000000000",
            "cnh": "99999999999",
            "cnh_category": "B",
            "cnh_expiry": _future_date(),
        },
        headers=operador_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_drivers(
    client: AsyncClient, admin_headers: dict[str, str], admin_user: object
) -> None:
    response = await client.get("/api/v1/drivers", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_delete_driver_allows_recreating_same_cpf(
    client: AsyncClient, operador_headers: dict[str, str], operador_user: object
) -> None:
    cpf = "11144477735"
    cnh = "11223344556"
    payload = {
        "nome": "Motorista Temporário",
        "cpf": cpf,
        "cnh": cnh,
        "cnh_category": "E",
        "cnh_expiry": _future_date(),
    }
    create_resp = await client.post("/api/v1/drivers", json=payload, headers=operador_headers)
    assert create_resp.status_code == 201
    driver_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/v1/drivers/{driver_id}", headers=operador_headers)
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/api/v1/drivers/{driver_id}", headers=operador_headers)
    assert get_resp.status_code == 404

    recreate_resp = await client.post("/api/v1/drivers", json=payload, headers=operador_headers)
    assert recreate_resp.status_code == 201
    assert recreate_resp.json()["cpf"] == cpf


@pytest.mark.asyncio
async def test_delete_driver_preserves_fuel_refill(
    client: AsyncClient,
    operador_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    create_resp = await client.post(
        "/api/v1/drivers",
        json={
            "nome": "Motorista Com Abastecimento",
            "cpf": "39053344705",
            "cnh": "99887766554",
            "cnh_category": "D",
            "cnh_expiry": _future_date(),
        },
        headers=operador_headers,
    )
    assert create_resp.status_code == 201
    driver_id = create_resp.json()["id"]
    driver_name = create_resp.json()["name"]

    client_row = Client(
        nome="Cliente Histórico",
        cpf_cnpj="11222333000181",
        is_active=True,
        tenant_id=test_tenant.id,
    )
    db_session.add(client_row)
    await db_session.flush()

    freight = Freight(
        client_id=client_row.id,
        driver_id=driver_id,
        origem={"cidade": "CURITIBA", "estado": "PR", "logradouro": "RUA A"},
        destino={"cidade": "FLORIANÓPOLIS", "estado": "SC", "logradouro": "RUA B"},
        valor_frete=5000.0,
        status=FreightStatus.EM_TRANSPORTE,
        tenant_id=test_tenant.id,
    )
    db_session.add(freight)
    await db_session.commit()
    await db_session.refresh(freight)

    fuel_resp = await client.post(
        "/api/v1/fuel",
        json={
            "freight_id": str(freight.id),
            "driver_id": driver_id,
            "litros": 100,
            "valor_total": 500,
        },
        headers=operador_headers,
    )
    assert fuel_resp.status_code == 201
    fuel_id = fuel_resp.json()["id"]

    del_resp = await client.delete(f"/api/v1/drivers/{driver_id}", headers=operador_headers)
    assert del_resp.status_code == 204

    fuel_get = await client.get(f"/api/v1/fuel/{fuel_id}", headers=operador_headers)
    assert fuel_get.status_code == 200
    fuel_data = fuel_get.json()
    assert fuel_data["driver_id"] is None
    assert fuel_data["driver_name"] == driver_name
    assert fuel_data["litros"] == 100


@pytest.mark.asyncio
async def test_get_driver_not_found(
    client: AsyncClient, admin_headers: dict[str, str], admin_user: object
) -> None:
    import uuid
    response = await client.get(
        f"/api/v1/drivers/{uuid.uuid4()}",
        headers=admin_headers,
    )
    assert response.status_code == 404
