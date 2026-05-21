"""Tests for auth endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, admin_user: object) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Admin@123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, admin_user: object) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "WrongPassword!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@test.com", "password": "Password@123!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient, admin_user: object) -> None:
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Admin@123!"},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 200
    assert "access_token" in refresh_resp.json()


@pytest.mark.asyncio
async def test_logout(client: AsyncClient, admin_user: object) -> None:
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Admin@123!"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    logout_resp = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_resp.status_code == 200


@pytest.mark.asyncio
async def test_change_password_success(
    client: AsyncClient, admin_user: object, admin_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "Admin@123!", "new_password": "NewAdmin@456!"},
        headers=admin_headers,
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_forgot_password_always_returns_ok(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nonexistent@test.com"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
