"""Additional tests to boost service coverage."""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User


@pytest.mark.asyncio
async def test_delete_truck(
    client: AsyncClient,
    operador_headers: dict[str, str],
    operador_user: object,
) -> None:
    create_resp = await client.post(
        "/api/v1/trucks",
        json={
            "placa": "DEL1111",
            "modelo": "TGX",
            "marca": "MAN",
            "ano": 2020,
            "capacidade_kg": 22000.0,
        },
        headers=operador_headers,
    )
    assert create_resp.status_code == 201
    truck_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/v1/trucks/{truck_id}",
        headers=operador_headers,
    )
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/api/v1/trucks/{truck_id}", headers=operador_headers)
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_driver(
    client: AsyncClient,
    operador_headers: dict[str, str],
    operador_user: object,
) -> None:
    create_resp = await client.post(
        "/api/v1/drivers",
        json={
            "nome": "Driver para deletar",
            "cpf": "52998224725",
            "cnh": "55566677788",
            "cnh_category": "D",
            "cnh_expiry": (date.today() + timedelta(days=400)).isoformat(),
        },
        headers=operador_headers,
    )
    assert create_resp.status_code == 201
    driver_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/v1/drivers/{driver_id}",
        headers=operador_headers,
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_client(
    client: AsyncClient,
    operador_headers: dict[str, str],
    operador_user: object,
) -> None:
    create_resp = await client.post(
        "/api/v1/clients",
        json={"nome": "Cliente deletável", "cpf_cnpj": "52998224725"},
        headers=operador_headers,
    )
    assert create_resp.status_code == 201
    client_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/v1/clients/{client_id}",
        headers=operador_headers,
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_user_as_admin(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: User,
    db_session: AsyncSession,
) -> None:
    from app.core.security.password import hash_password
    from app.shared.enums import UserRole

    target = User(
        nome="User para Deletar",
        email="deleteme@test.com",
        hashed_password=hash_password("Del@123!"),
        role=UserRole.OPERADOR,
        is_active=True,
    )
    db_session.add(target)
    await db_session.commit()
    await db_session.refresh(target)

    del_resp = await client.delete(
        f"/api/v1/users/{target.id}",
        headers=admin_headers,
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_get_user_not_found(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: object,
) -> None:
    response = await client.get(
        f"/api/v1/users/{uuid.uuid4()}",
        headers=admin_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_trucks_with_filter(
    client: AsyncClient,
    operador_headers: dict[str, str],
    operador_user: object,
) -> None:
    response = await client.get(
        "/api/v1/trucks?status=disponivel",
        headers=operador_headers,
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_drivers_with_filter(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: object,
) -> None:
    response = await client.get(
        "/api/v1/drivers?status=ativo&search=motorista",
        headers=admin_headers,
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_clients_with_filter(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: object,
) -> None:
    response = await client.get(
        "/api/v1/clients?is_active=true&search=test",
        headers=admin_headers,
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_freights_with_filter(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: object,
) -> None:
    response = await client.get(
        "/api/v1/freights?status=orcamento&page=1&size=10",
        headers=admin_headers,
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_finance_entry_update_and_delete(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    from app.core.security.jwt import create_access_token
    from app.core.security.password import hash_password
    from app.shared.enums import UserRole

    fin_user = User(
        nome="Financeiro Cover",
        email=f"fincov_{uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("Fin@123!"),
        role=UserRole.FINANCEIRO,
        is_active=True,
    )
    db_session.add(fin_user)
    await db_session.commit()
    await db_session.refresh(fin_user)
    token = create_access_token(fin_user.id, fin_user.role)
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await client.post(
        "/api/v1/finance",
        json={
            "tipo": "despesa",
            "categoria": "Combustível",
            "descricao": "Abastecimento SP",
            "valor": 800.0,
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    entry_id = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/api/v1/finance/{entry_id}",
        json={"status": "pago"},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "pago"

    del_resp = await client.delete(f"/api/v1/finance/{entry_id}", headers=headers)
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_list_finance_with_filter(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    from app.core.security.jwt import create_access_token
    from app.core.security.password import hash_password
    from app.shared.enums import UserRole

    fin_user = User(
        nome="Financeiro Filter",
        email=f"finflt_{uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("Fin@123!"),
        role=UserRole.FINANCEIRO,
        is_active=True,
    )
    db_session.add(fin_user)
    await db_session.commit()
    await db_session.refresh(fin_user)
    token = create_access_token(fin_user.id, fin_user.role)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(
        "/api/v1/finance?tipo=receita&status=pendente&categoria=Frete",
        headers=headers,
    )
    assert response.status_code == 200
