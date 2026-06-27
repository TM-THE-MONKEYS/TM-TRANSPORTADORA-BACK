"""Tests for driver commission expense on freight delivery."""
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
from app.modules.users.models import User
from app.shared.enums import CNHCategory, DriverStatus, FreightStatus, UserRole


async def _setup_commission_freight(
    db_session: AsyncSession,
    test_tenant: object,
    *,
    commission_pct: float | None = 8.0,
    valor_frete: float = 10000.0,
    driver_id: bool = True,
) -> tuple[Freight, Driver | None]:
    client_row = Client(
        nome="Cliente Comissão",
        cpf_cnpj=f"{uuid.uuid4().hex[:14]}",
        is_active=True,
        tenant_id=test_tenant.id,  # type: ignore[attr-defined]
    )
    db_session.add(client_row)
    await db_session.flush()

    driver: Driver | None = None
    if driver_id:
        driver = Driver(
            nome="João Motorista",
            cpf=f"{uuid.uuid4().hex[:11]}",
            cnh=f"{uuid.uuid4().hex[:11]}",
            cnh_category=CNHCategory.C,
            cnh_expiry=date(2030, 12, 31),
            status=DriverStatus.ATIVO,
            commission_pct=commission_pct,
            tenant_id=test_tenant.id,  # type: ignore[attr-defined]
        )
        db_session.add(driver)
        await db_session.flush()

    freight = Freight(
        client_id=client_row.id,
        driver_id=driver.id if driver else None,
        origem={"cidade": "São Paulo", "estado": "SP", "logradouro": "Rua A"},
        destino={"cidade": "Rio de Janeiro", "estado": "RJ", "logradouro": "Rua B"},
        valor_frete=valor_frete,
        status=FreightStatus.EM_TRANSPORTE,
        tenant_id=test_tenant.id,  # type: ignore[attr-defined]
    )
    db_session.add(freight)
    await db_session.commit()
    await db_session.refresh(freight)
    if driver:
        await db_session.refresh(driver)
    return freight, driver


async def _financeiro_headers(db_session: AsyncSession, test_tenant: object) -> dict[str, str]:
    user = User(
        nome="Financeiro Comissão",
        email="fin.comissao@test.com",
        hashed_password=hash_password("Fin@123!"),
        role=UserRole.FINANCEIRO,
        is_active=True,
        tenant_id=test_tenant.id,  # type: ignore[attr-defined]
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token = create_access_token(user.id, user.role, tenant_id=user.tenant_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_commission_expense_on_delivered_freight(
    client: AsyncClient,
    operador_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: object,
) -> None:
    freight, _ = await _setup_commission_freight(db_session, test_tenant)
    fin_headers = await _financeiro_headers(db_session, test_tenant)

    status_resp = await client.patch(
        f"/api/v1/freights/{freight.id}/status",
        json={"status": "entregue"},
        headers=operador_headers,
    )
    assert status_resp.status_code == 200

    finance_resp = await client.get(
        f"/api/v1/finance?freight_id={freight.id}&categoria=Comissão",
        headers=fin_headers,
    )
    assert finance_resp.status_code == 200
    items = finance_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["categoria"] == "Comissão"
    assert items[0]["tipo"] == "despesa"
    assert items[0]["valor"] == 800.0
    assert items[0]["status"] == "pendente"


@pytest.mark.asyncio
async def test_commission_not_duplicated_on_second_delivery_or_sync(
    client: AsyncClient,
    operador_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: object,
) -> None:
    freight, _ = await _setup_commission_freight(db_session, test_tenant)
    fin_headers = await _financeiro_headers(db_session, test_tenant)

    await client.patch(
        f"/api/v1/freights/{freight.id}/status",
        json={"status": "entregue"},
        headers=operador_headers,
    )
    sync_resp = await client.post("/api/v1/finance/sync-from-freights", headers=fin_headers)
    assert sync_resp.status_code == 200

    finance_resp = await client.get(
        f"/api/v1/finance?freight_id={freight.id}&categoria=Comissão",
        headers=fin_headers,
    )
    assert len(finance_resp.json()["items"]) == 1


@pytest.mark.asyncio
async def test_no_commission_without_driver_or_pct(
    client: AsyncClient,
    operador_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: object,
) -> None:
    freight_no_driver, _ = await _setup_commission_freight(
        db_session, test_tenant, driver_id=False
    )
    fin_headers = await _financeiro_headers(db_session, test_tenant)

    await client.patch(
        f"/api/v1/freights/{freight_no_driver.id}/status",
        json={"status": "entregue"},
        headers=operador_headers,
    )

    resp = await client.get(
        f"/api/v1/finance?freight_id={freight_no_driver.id}&categoria=Comissão",
        headers=fin_headers,
    )
    assert resp.json()["items"] == []

    freight_zero_pct, _ = await _setup_commission_freight(
        db_session, test_tenant, commission_pct=0
    )
    await client.patch(
        f"/api/v1/freights/{freight_zero_pct.id}/status",
        json={"status": "entregue"},
        headers=operador_headers,
    )
    resp2 = await client.get(
        f"/api/v1/finance?freight_id={freight_zero_pct.id}&categoria=Comissão",
        headers=fin_headers,
    )
    assert resp2.json()["items"] == []
