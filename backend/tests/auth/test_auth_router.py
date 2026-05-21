"""Tests for auth endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


def _extract_tokens(data: dict) -> tuple[str, str]:
    """Extract access and refresh tokens from the new login response shape."""
    if "tokens" in data:
        return data["tokens"]["access_token"], data["tokens"]["refresh_token"]
    return data["access_token"], data["refresh_token"]


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, admin_user: object) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Admin@123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "tokens" in data
    assert "user" in data
    assert data["tokens"]["token_type"] == "bearer"
    assert "access_token" in data["tokens"]
    assert "refresh_token" in data["tokens"]
    assert data["user"]["email"] == "admin@test.com"


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
    _, refresh_token = _extract_tokens(login_resp.json())

    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 200
    assert "tokens" in refresh_resp.json()
    assert "access_token" in refresh_resp.json()["tokens"]


@pytest.mark.asyncio
async def test_logout(client: AsyncClient, admin_user: object) -> None:
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Admin@123!"},
    )
    _, refresh_token = _extract_tokens(login_resp.json())

    logout_resp = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_resp.status_code == 200


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, admin_user: object, admin_headers: dict[str, str]) -> None:
    response = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "admin@test.com"
    assert "permissions" in data
    assert "name" in data


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
