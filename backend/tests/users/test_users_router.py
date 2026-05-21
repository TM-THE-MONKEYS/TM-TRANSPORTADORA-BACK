"""Tests for user endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, admin_headers: dict[str, str]) -> None:
    response = await client.get("/api/v1/users/me", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "admin@test.com"
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_users_admin_only(
    client: AsyncClient,
    admin_headers: dict[str, str],
    operador_headers: dict[str, str],
    admin_user: object,
    operador_user: object,
) -> None:
    admin_resp = await client.get("/api/v1/users", headers=admin_headers)
    assert admin_resp.status_code == 200

    operador_resp = await client.get("/api/v1/users", headers=operador_headers)
    assert operador_resp.status_code == 403


@pytest.mark.asyncio
async def test_create_user(
    client: AsyncClient, admin_headers: dict[str, str], admin_user: object
) -> None:
    response = await client.post(
        "/api/v1/users",
        json={
            "nome": "Novo Usuário",
            "email": "novo@test.com",
            "password": "Novo@123!",
            "role": "operador",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "novo@test.com"
    assert data["role"] == "operador"


@pytest.mark.asyncio
async def test_create_user_duplicate_email(
    client: AsyncClient, admin_headers: dict[str, str], admin_user: object
) -> None:
    response = await client.post(
        "/api/v1/users",
        json={
            "nome": "Duplicado",
            "email": "admin@test.com",
            "password": "Dup@123!",
            "role": "operador",
        },
        headers=admin_headers,
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_user_weak_password(
    client: AsyncClient, admin_headers: dict[str, str], admin_user: object
) -> None:
    response = await client.post(
        "/api/v1/users",
        json={
            "nome": "Fraco",
            "email": "fraco@test.com",
            "password": "weak",
            "role": "operador",
        },
        headers=admin_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_own_profile(
    client: AsyncClient, admin_headers: dict[str, str], admin_user: object
) -> None:
    get_me = await client.get("/api/v1/users/me", headers=admin_headers)
    user_id = get_me.json()["id"]

    response = await client.patch(
        f"/api/v1/users/{user_id}",
        json={"nome": "Admin Atualizado"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["nome"] == "Admin Atualizado"
