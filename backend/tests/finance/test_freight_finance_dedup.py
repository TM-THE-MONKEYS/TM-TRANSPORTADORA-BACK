"""Anti-duplicação frete ↔ financeiro."""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.modules.clients.models import Client
from app.modules.finance.freight_sync import (
    SOURCE_COST,
    SOURCE_FUEL,
    normalize_cost_tipo,
)
from app.modules.finance.models import FinanceEntry
from app.modules.freights.models import Freight
from app.modules.users.models import User
from app.shared.enums import FinanceEntryStatus, FinanceEntryType, FreightStatus, UserRole


def test_normalize_cost_tipo_strips_accents() -> None:
    assert "PEDAGIO" in normalize_cost_tipo("Pedágio")
    assert "PEDAGIO" in normalize_cost_tipo("PEDÁGIO")
    assert "COMBUST" in normalize_cost_tipo("combustível")


async def _freight(db_session: AsyncSession, test_tenant: object) -> Freight:
    client_row = Client(
        nome="Cliente Dedup",
        cpf_cnpj=f"{uuid.uuid4().hex[:14]}",
        is_active=True,
        tenant_id=test_tenant.id,  # type: ignore[attr-defined]
    )
    db_session.add(client_row)
    await db_session.flush()
    freight = Freight(
        client_id=client_row.id,
        origem={"cidade": "SP", "estado": "SP", "logradouro": "Rua A"},
        destino={"cidade": "RJ", "estado": "RJ", "logradouro": "Rua B"},
        valor_frete=5000.0,
        status=FreightStatus.EM_TRANSPORTE,
        tenant_id=test_tenant.id,  # type: ignore[attr-defined]
    )
    db_session.add(freight)
    await db_session.commit()
    await db_session.refresh(freight)
    return freight


@pytest.mark.asyncio
async def test_manual_fuel_cost_blocked(
    client: AsyncClient,
    operador_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: object,
) -> None:
    freight = await _freight(db_session, test_tenant)
    response = await client.post(
        f"/api/v1/freights/{freight.id}/costs",
        json={"tipo": "combustivel", "valor": 200.0, "descricao": "posto"},
        headers=operador_headers,
    )
    assert response.status_code == 400
    assert "Abastecimento" in response.json()["detail"]


@pytest.mark.asyncio
async def test_manual_pedagio_creates_single_finance_entry(
    client: AsyncClient,
    operador_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: object,
) -> None:
    freight = await _freight(db_session, test_tenant)
    response = await client.post(
        f"/api/v1/freights/{freight.id}/costs",
        json={"tipo": "pedagio", "valor": 85.5, "descricao": "Pedágio Anhanguera"},
        headers=operador_headers,
    )
    assert response.status_code == 201, response.text
    cost_id = response.json()["id"]

    entries = (
        await db_session.execute(
            select(FinanceEntry).where(
                FinanceEntry.freight_id == freight.id,
                FinanceEntry.deleted_at.is_(None),
                FinanceEntry.tipo == FinanceEntryType.DESPESA,
            )
        )
    ).scalars().all()
    pedagio = [e for e in entries if e.observacoes == f"{SOURCE_COST}{cost_id}"]
    assert len(pedagio) == 1
    assert pedagio[0].valor == 85.5
    assert pedagio[0].categoria == "Pedágio"


@pytest.mark.asyncio
async def test_cash_flow_excludes_cancelled(
    client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: object,
) -> None:
    user = User(
        nome="Fin Dedup",
        email=f"fin.dedup.{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hash_password("Fin@123!"),
        role=UserRole.FINANCEIRO,
        is_active=True,
        tenant_id=test_tenant.id,  # type: ignore[attr-defined]
    )
    db_session.add(user)
    db_session.add(
        FinanceEntry(
            tipo=FinanceEntryType.DESPESA,
            categoria="Teste",
            descricao="Ativa",
            valor=100.0,
            status=FinanceEntryStatus.PAGO,
            data_pagamento=date.today(),
            tenant_id=test_tenant.id,  # type: ignore[attr-defined]
        )
    )
    db_session.add(
        FinanceEntry(
            tipo=FinanceEntryType.DESPESA,
            categoria="Teste",
            descricao="Cancelada fantasma",
            valor=999.0,
            status=FinanceEntryStatus.CANCELADO,
            data_pagamento=date.today(),
            tenant_id=test_tenant.id,  # type: ignore[attr-defined]
        )
    )
    await db_session.commit()
    await db_session.refresh(user)

    token = create_access_token(user.id, user.role, tenant_id=user.tenant_id)
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/api/v1/finance/cash-flow", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_despesas"] == 100.0
    assert 999.0 not in (data["total_despesas"],)


@pytest.mark.asyncio
async def test_fuel_delete_soft_deletes_finance_mirror(
    client: AsyncClient,
    operador_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: object,
) -> None:
    from app.modules.drivers.models import Driver
    from app.modules.trucks.models import Truck
    from app.shared.enums import CNHCategory, DriverStatus, TruckStatus

    client_row = Client(
        nome="Cliente Fuel",
        cpf_cnpj=f"{uuid.uuid4().hex[:14]}",
        is_active=True,
        tenant_id=test_tenant.id,  # type: ignore[attr-defined]
    )
    driver = Driver(
        nome="Motorista Fuel",
        cpf=f"{uuid.uuid4().hex[:11]}",
        cnh=f"{uuid.uuid4().hex[:11]}",
        cnh_category=CNHCategory.C,
        cnh_expiry=date(2030, 12, 31),
        status=DriverStatus.ATIVO,
        tenant_id=test_tenant.id,  # type: ignore[attr-defined]
    )
    truck = Truck(
        placa=f"FD{uuid.uuid4().hex[:5].upper()}",
        marca="Volvo",
        modelo="FH",
        ano=2020,
        capacidade_kg=20000.0,
        status=TruckStatus.DISPONIVEL,
        km_atual=10000,
        tenant_id=test_tenant.id,  # type: ignore[attr-defined]
    )
    db_session.add_all([client_row, driver, truck])
    await db_session.flush()

    freight = Freight(
        client_id=client_row.id,
        driver_id=driver.id,
        truck_id=truck.id,
        origem={"cidade": "SP", "estado": "SP", "logradouro": "Rua A"},
        destino={"cidade": "RJ", "estado": "RJ", "logradouro": "Rua B"},
        valor_frete=3000.0,
        status=FreightStatus.EM_TRANSPORTE,
        tenant_id=test_tenant.id,  # type: ignore[attr-defined]
    )
    db_session.add(freight)
    await db_session.commit()
    await db_session.refresh(freight)

    create_resp = await client.post(
        "/api/v1/fuel",
        json={
            "freight_id": str(freight.id),
            "litros": 50,
            "valor_total": 400.0,
            "km_atual": 10100,
            "posto": "Shell",
        },
        headers=operador_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    refill_id = create_resp.json()["id"]

    mirror = (
        await db_session.execute(
            select(FinanceEntry).where(
                FinanceEntry.observacoes == f"{SOURCE_FUEL}{refill_id}",
                FinanceEntry.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    assert mirror is not None

    del_resp = await client.delete(f"/api/v1/fuel/{refill_id}", headers=operador_headers)
    assert del_resp.status_code == 204, del_resp.text

    db_session.expire_all()
    gone = (
        await db_session.execute(
            select(FinanceEntry).where(
                FinanceEntry.observacoes == f"{SOURCE_FUEL}{refill_id}",
                FinanceEntry.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    assert gone is None
