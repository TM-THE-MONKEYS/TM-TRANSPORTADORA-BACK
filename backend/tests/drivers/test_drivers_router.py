"""Tests for driver endpoints."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import AsyncClient


def _future_date() -> str:
    return (date.today() + timedelta(days=365)).isoformat()


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
    assert data["name"] == "João Motorista"
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
    assert data["name"] == "Maria Motorista"
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
async def test_get_driver_not_found(
    client: AsyncClient, admin_headers: dict[str, str], admin_user: object
) -> None:
    import uuid
    response = await client.get(
        f"/api/v1/drivers/{uuid.uuid4()}",
        headers=admin_headers,
    )
    assert response.status_code == 404
