"""Tests for client endpoints."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_client_with_valid_cpf(
    client: AsyncClient, operador_headers: dict[str, str], operador_user: object
) -> None:
    response = await client.post(
        "/api/v1/clients",
        json={
            "nome": "Cliente Teste",
            "cpf_cnpj": "52998224725",
            "email": "cliente@test.com",
            "telefone": "11999999999",
        },
        headers=operador_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["nome"] == "Cliente Teste"
    assert data["cpf_cnpj"] == "52998224725"


@pytest.mark.asyncio
async def test_create_client_invalid_doc(
    client: AsyncClient, operador_headers: dict[str, str], operador_user: object
) -> None:
    response = await client.post(
        "/api/v1/clients",
        json={
            "nome": "Doc Inválido",
            "cpf_cnpj": "00000000000",
        },
        headers=operador_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_clients(
    client: AsyncClient, admin_headers: dict[str, str], admin_user: object
) -> None:
    response = await client.get("/api/v1/clients", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data


@pytest.mark.asyncio
async def test_get_client_not_found(
    client: AsyncClient, admin_headers: dict[str, str], admin_user: object
) -> None:
    response = await client.get(
        f"/api/v1/clients/{uuid.uuid4()}",
        headers=admin_headers,
    )
    assert response.status_code == 404
