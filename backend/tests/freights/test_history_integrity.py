"""Fase 1: data de pagamento, datas reais, histórico e purga."""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client
from app.modules.drivers.models import Driver
from app.modules.finance.models import FinanceEntry
from app.modules.freights.models import Freight, FreightCost
from app.modules.fuel.models import FuelRefill
from app.modules.status_history.models import StatusHistory
from app.modules.tenants.models import Tenant
from app.modules.trucks.models import Truck
from app.shared.enums import CNHCategory, DriverStatus, FreightStatus, TruckStatus
from app.shared.utils.dates import today_sp


async def _client(db_session: AsyncSession, tenant: Tenant) -> Client:
    row = Client(
        nome="Cliente Histórico",
        cpf_cnpj=f"{uuid.uuid4().int % 10**14:014d}",
        tenant_id=tenant.id,
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


@pytest.mark.asyncio
async def test_paid_revenue_is_grouped_by_payment_date(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    created = await client.post(
        "/api/v1/finance",
        json={
            "tipo": "receita",
            "categoria": "Frete",
            "descricao": "Criada antes e paga agora",
            "valor": 1500,
            "status": "pendente",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    entry_id = created.json()["id"]

    paid = await client.patch(
        f"/api/v1/finance/{entry_id}",
        json={"status": "pago"},
        headers=admin_headers,
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["data_pagamento"] == today_sp().isoformat()

    entry = await db_session.get(FinanceEntry, uuid.UUID(entry_id))
    assert entry is not None
    entry.created_at = datetime.now(UTC) - timedelta(days=90)
    await db_session.commit()

    old_payment = (today_sp() - timedelta(days=90)).isoformat()
    outside = await client.post(
        "/api/v1/finance",
        json={
            "tipo": "receita",
            "categoria": "Frete",
            "descricao": "Paga fora da janela",
            "valor": 999,
            "status": "pago",
            "data_pagamento": old_payment,
        },
        headers=admin_headers,
    )
    assert outside.status_code == 201, outside.text
    assert outside.json()["data_pagamento"] == old_payment

    series = await client.get(
        "/api/v1/dashboard/revenue-series?days=30",
        headers=admin_headers,
    )
    assert series.status_code == 200, series.text
    points = {row["date"]: row["revenue"] for row in series.json()}
    assert points.get(today_sp().isoformat()) == 1500
    assert old_payment not in points


@pytest.mark.asyncio
async def test_collection_and_delivery_dates_and_history(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    db_client = await _client(db_session, test_tenant)
    created = await client.post(
        "/api/v1/freights",
        json={
            "client_id": str(db_client.id),
            "origem": {"logradouro": "Rua A", "cidade": "São Paulo", "estado": "SP"},
            "destino": {"logradouro": "Rua B", "cidade": "Curitiba", "estado": "PR"},
            "valor_frete": 2200,
            "status": "em_transporte",
            "data_coleta": "2026-08-01",
            "data_entrega_prevista": "2027-12-31",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    freight_id = created.json()["id"]
    body = created.json()
    assert body["coletado_em"] is not None
    assert body["delivered_at"] is None

    db_session.expire_all()
    freight = await db_session.get(Freight, uuid.UUID(freight_id))
    assert freight is not None
    assert freight.data_coleta is not None
    coleta = freight.data_coleta
    assert coleta.month == 8 and coleta.day == 1
    assert freight.coletado_em is not None
    assert freight.coletado_em.date() != date(2026, 8, 1)

    delivered = await client.post(
        f"/api/v1/freights/{freight_id}/advance-status",
        headers=admin_headers,
    )
    assert delivered.status_code == 200, delivered.text
    assert delivered.json()["delivered_at"] is not None
    assert delivered.json()["delivery_real_origin"] == "registrada"

    history = await client.get(
        f"/api/v1/freights/{freight_id}/history",
        headers=admin_headers,
    )
    assert history.status_code == 200, history.text
    rows = history.json()
    assert rows[0]["from_status"] is None
    assert rows[0]["to_status"] == "em_transporte"
    assert rows[0]["source"] == "api"
    assert rows[-1]["to_status"] == "entregue"

    kpis = await client.get("/api/v1/dashboard/kpis", headers=admin_headers)
    assert kpis.status_code == 200, kpis.text
    assert kpis.json()["on_time_deliveries"] == 1
    assert kpis.json()["deliveries_with_deadline"] == 1

    reopened = await client.patch(
        f"/api/v1/freights/{freight_id}/status",
        json={"status": "em_transporte"},
        headers=admin_headers,
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["delivered_at"] is None
    assert reopened.json()["delivery_real_origin"] is None

    history = await client.get(
        f"/api/v1/freights/{freight_id}/history",
        headers=admin_headers,
    )
    reopen = history.json()[-1]
    assert reopen["from_status"] == "entregue"
    assert reopen["to_status"] == "em_transporte"
    assert "data_entrega_real limpa" in (reopen["motivo"] or "")


@pytest.mark.asyncio
async def test_on_time_respects_competencia_and_late_delivery(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    db_client = await _client(db_session, test_tenant)
    late = await client.post(
        "/api/v1/freights",
        json={
            "client_id": str(db_client.id),
            "origem": {"logradouro": "Rua A", "cidade": "São Paulo", "estado": "SP"},
            "destino": {"logradouro": "Rua B", "cidade": "Recife", "estado": "PE"},
            "valor_frete": 800,
            "status": "em_transporte",
            "data_entrega_prevista": "2020-01-15",
        },
        headers=admin_headers,
    )
    assert late.status_code == 201, late.text
    freight_id = late.json()["id"]
    advanced = await client.post(
        f"/api/v1/freights/{freight_id}/advance-status",
        headers=admin_headers,
    )
    assert advanced.status_code == 200, advanced.text

    kpis = await client.get("/api/v1/dashboard/kpis", headers=admin_headers)
    assert kpis.json()["on_time_deliveries"] == 0
    assert kpis.json()["deliveries_with_deadline"] == 1

    filtered = await client.get(
        "/api/v1/dashboard/kpis?competencia_mes=1&competencia_ano=2020",
        headers=admin_headers,
    )
    assert filtered.json()["deliveries_with_deadline"] == 0


@pytest.mark.asyncio
async def test_tracking_delivery_records_history_and_dates(
    client: AsyncClient,
    operador_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    db_client = await _client(db_session, test_tenant)
    freight = Freight(
        client_id=db_client.id,
        origem={"cidade": "São Paulo", "estado": "SP", "logradouro": "Rua A"},
        destino={"cidade": "Rio de Janeiro", "estado": "RJ", "logradouro": "Rua B"},
        valor_frete=900,
        status=FreightStatus.ORCAMENTO,
        tenant_id=test_tenant.id,
    )
    db_session.add(freight)
    await db_session.commit()
    await db_session.refresh(freight)
    freight_id = freight.id

    response = await client.post(
        "/api/v1/tracking",
        json={
            "freight_id": str(freight_id),
            "status": "entregue",
            "descricao": "Entrega registrada",
        },
        headers=operador_headers,
    )
    assert response.status_code == 201, response.text

    history = await client.get(
        f"/api/v1/freights/{freight_id}/history",
        headers=operador_headers,
    )
    assert history.status_code == 200, history.text
    rows = history.json()
    assert [row["to_status"] for row in rows] == ["em_transporte", "entregue"]
    assert all(row["source"] == "tracking" for row in rows)

    db_session.expire_all()
    refreshed = await db_session.get(Freight, freight_id)
    assert refreshed is not None
    assert refreshed.coletado_em is not None
    assert refreshed.data_entrega_real is not None
    assert refreshed.data_entrega_real_origem == "registrada"


@pytest.mark.asyncio
async def test_truck_sync_and_driver_status_are_historized(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    db_client = await _client(db_session, test_tenant)
    truck = Truck(
        placa=f"HIS{uuid.uuid4().hex[:4].upper()}",
        modelo="FH",
        marca="Volvo",
        ano=2022,
        capacidade_kg=20000,
        km_atual=1000,
        status=TruckStatus.DISPONIVEL,
        tenant_id=test_tenant.id,
    )
    driver = Driver(
        nome="Motorista Histórico",
        cpf=f"{uuid.uuid4().int % 10**11:011d}",
        cnh=f"{uuid.uuid4().int % 10**11:011d}",
        cnh_category=CNHCategory.E,
        cnh_expiry=date(2030, 1, 1),
        status=DriverStatus.ATIVO,
        tenant_id=test_tenant.id,
    )
    db_session.add_all([truck, driver])
    await db_session.commit()
    tenant_id = test_tenant.id
    truck_id = truck.id
    driver_id = driver.id

    created = await client.post(
        "/api/v1/freights",
        json={
            "client_id": str(db_client.id),
            "truck_id": str(truck_id),
            "origem": {"logradouro": "Rua A", "cidade": "São Paulo", "estado": "SP"},
            "destino": {"logradouro": "Rua B", "cidade": "Santos", "estado": "SP"},
            "valor_frete": 500,
            "status": "em_transporte",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text

    patched = await client.patch(
        f"/api/v1/drivers/{driver_id}",
        json={"status": "ferias"},
        headers=admin_headers,
    )
    assert patched.status_code == 200, patched.text

    db_session.expire_all()
    rows = list(
        (
            await db_session.execute(
                select(StatusHistory).where(StatusHistory.tenant_id == tenant_id)
            )
        ).scalars()
    )
    assert any(
        row.entity_type == "truck"
        and row.to_status == "em_viagem"
        and row.source == "system"
        for row in rows
    )
    assert any(
        row.entity_type == "driver"
        and row.from_status == "ativo"
        and row.to_status == "ferias"
        and row.source == "api"
        for row in rows
    )


@pytest.mark.asyncio
async def test_purge_removes_rows_and_requires_admin_confirmation(
    client: AsyncClient,
    admin_headers: dict[str, str],
    operador_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    db_client = await _client(db_session, test_tenant)
    created = await client.post(
        "/api/v1/freights",
        json={
            "client_id": str(db_client.id),
            "origem": {"logradouro": "Rua A", "cidade": "São Paulo", "estado": "SP"},
            "destino": {"logradouro": "Rua B", "cidade": "Santos", "estado": "SP"},
            "valor_frete": 400,
            "status": "orcamento",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    freight_id = created.json()["id"]
    fid = uuid.UUID(freight_id)

    cost_resp = await client.post(
        f"/api/v1/freights/{freight_id}/costs",
        json={"tipo": "outro", "valor": 10, "descricao": "Teste"},
        headers=admin_headers,
    )
    assert cost_resp.status_code == 201, cost_resp.text
    cost_id = uuid.UUID(cost_resp.json()["id"])

    fuel = FuelRefill(
        tenant_id=test_tenant.id,
        freight_id=fid,
        litros=10,
        valor_total=50,
        data_abastecimento=datetime.now(UTC),
    )
    db_session.add(fuel)
    await db_session.commit()
    fuel_id = fuel.id

    missing = await client.delete(
        f"/api/v1/freights/{freight_id}?purge=true",
        headers=admin_headers,
    )
    assert missing.status_code == 400

    forbidden = await client.delete(
        f"/api/v1/freights/{freight_id}?purge=true&confirmacao=PURGAR",
        headers=operador_headers,
    )
    assert forbidden.status_code == 403

    purged = await client.delete(
        f"/api/v1/freights/{freight_id}?purge=true&confirmacao=PURGAR",
        headers=admin_headers,
    )
    assert purged.status_code == 204, purged.text

    db_session.expire_all()
    assert await db_session.get(Freight, fid) is None
    assert await db_session.get(FreightCost, cost_id) is None
    assert await db_session.get(FuelRefill, fuel_id) is None
