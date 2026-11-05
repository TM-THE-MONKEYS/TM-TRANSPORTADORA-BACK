"""Fase 2: consumo, alertas km/CNH e campos de negócio."""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client
from app.modules.drivers.models import Driver
from app.modules.freights.models import Freight
from app.modules.fuel.models import FuelRefill
from app.modules.maintenance.models import Maintenance
from app.modules.tenants.models import Tenant
from app.modules.trucks.models import Truck
from app.shared.enums import (
    CNHCategory,
    DriverStatus,
    FreightStatus,
    MaintenanceStatus,
    MaintenanceType,
    TruckStatus,
)
from app.shared.utils.dates import today_sp


async def _client(db: AsyncSession, tenant: Tenant) -> Client:
    row = Client(
        nome="Cliente Fase2",
        cpf_cnpj=f"{uuid.uuid4().int % 10**14:014d}",
        tenant_id=tenant.id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@pytest.mark.asyncio
async def test_truck_consumption_between_full_tanks(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    truck = Truck(
        placa=f"F2{uuid.uuid4().hex[:5].upper()}",
        modelo="FH",
        marca="Volvo",
        ano=2022,
        capacidade_kg=20000,
        km_atual=12000,
        consumo_km_l=3.0,
        status=TruckStatus.DISPONIVEL,
        tenant_id=test_tenant.id,
    )
    db_client = await _client(db_session, test_tenant)
    freight = Freight(
        client_id=db_client.id,
        truck_id=None,
        origem={"cidade": "SP", "estado": "SP", "logradouro": "A"},
        destino={"cidade": "RJ", "estado": "RJ", "logradouro": "B"},
        valor_frete=100,
        status=FreightStatus.EM_TRANSPORTE,
        tenant_id=test_tenant.id,
    )
    db_session.add_all([truck, freight])
    await db_session.commit()
    await db_session.refresh(truck)
    await db_session.refresh(freight)
    freight.truck_id = truck.id
    await db_session.commit()

    now = datetime.now(UTC)
    for km, litros, full in ((10000, 300, True), (10300, 100, True)):
        db_session.add(
            FuelRefill(
                freight_id=freight.id,
                truck_id=truck.id,
                litros=litros,
                valor_total=litros * 6,
                km_atual=km,
                tanque_cheio=full,
                data_abastecimento=now,
                tenant_id=test_tenant.id,
            )
        )
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/trucks/{truck.id}/consumption",
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["consumo_real_km_l"] == pytest.approx(3.0)
    assert body["desvio_relevante"] is False
    assert len(body["segmentos"]) == 1
    assert body["custo_combustivel"] == pytest.approx(2400.0)


@pytest.mark.asyncio
async def test_maintenance_alert_by_km(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    truck = Truck(
        placa=f"KM{uuid.uuid4().hex[:5].upper()}",
        modelo="FH",
        marca="Volvo",
        ano=2021,
        capacidade_kg=20000,
        km_atual=9950,
        status=TruckStatus.DISPONIVEL,
        tenant_id=test_tenant.id,
    )
    db_session.add(truck)
    await db_session.commit()
    await db_session.refresh(truck)

    maint = Maintenance(
        truck_id=truck.id,
        tipo=MaintenanceType.PREVENTIVA,
        descricao="Troca óleo",
        status=MaintenanceStatus.AGENDADA,
        km_proxima=10000,
        data_prevista=datetime.now(UTC) + timedelta(days=90),
        tenant_id=test_tenant.id,
    )
    db_session.add(maint)
    await db_session.commit()

    alerts = await client.get("/api/v1/maintenance/alerts", headers=admin_headers)
    assert alerts.status_code == 200, alerts.text
    ids = {row["id"] for row in alerts.json()}
    assert str(maint.id) in ids


@pytest.mark.asyncio
async def test_cnh_alerts_and_dashboard_kpi(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    driver = Driver(
        nome="Motorista CNH",
        cpf=f"{uuid.uuid4().int % 10**11:011d}",
        cnh=f"{uuid.uuid4().int % 10**11:011d}",
        cnh_category=CNHCategory.E,
        cnh_expiry=today_sp() + timedelta(days=10),
        status=DriverStatus.ATIVO,
        tenant_id=test_tenant.id,
    )
    db_session.add(driver)
    await db_session.commit()

    alerts = await client.get(
        "/api/v1/drivers/alerts?days_ahead=30",
        headers=admin_headers,
    )
    assert alerts.status_code == 200, alerts.text
    assert any(row["id"] == str(driver.id) for row in alerts.json())

    kpis = await client.get("/api/v1/dashboard/kpis", headers=admin_headers)
    assert kpis.status_code == 200, kpis.text
    assert kpis.json()["cnh_alerts"] >= 1


@pytest.mark.asyncio
async def test_cancel_requires_motivo_and_rankings(
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
            "origem": {"logradouro": "A", "cidade": "SP", "estado": "SP"},
            "destino": {"logradouro": "B", "cidade": "RJ", "estado": "RJ"},
            "valor_frete": 400,
            "status": "em_transporte",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    fid = created.json()["id"]

    bad = await client.patch(
        f"/api/v1/freights/{fid}/status",
        json={"status": "cancelado"},
        headers=admin_headers,
    )
    assert bad.status_code == 400, bad.text

    ok = await client.patch(
        f"/api/v1/freights/{fid}/status",
        json={
            "status": "cancelado",
            "motivo_cancelamento": "cliente_desistiu",
            "motivo_cancelamento_detalhe": "Mudou de ideia",
        },
        headers=admin_headers,
    )
    assert ok.status_code == 200, ok.text

    ranking = await client.get(
        "/api/v1/freights/analytics/reasons",
        headers=admin_headers,
    )
    assert ranking.status_code == 200, ranking.text
    reasons = {row["reason"] for row in ranking.json()["cancelamentos"]}
    assert "cliente_desistiu" in reasons


@pytest.mark.asyncio
async def test_forma_pagamento_and_client_prazo(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    # CNPJ válido conhecido (checksum). Sufixo aleatório evitado de propósito.
    client_resp = await client.post(
        "/api/v1/clients",
        json={
            "nome": "Cliente Prazo",
            "cpf_cnpj": "11444777000161",
            "prazo_pagamento_dias": 15,
        },
        headers=admin_headers,
    )
    assert client_resp.status_code == 201, client_resp.text
    assert client_resp.json()["prazo_pagamento_dias"] == 15

    entry = await client.post(
        "/api/v1/finance",
        json={
            "tipo": "receita",
            "categoria": "Frete",
            "descricao": "Com PIX",
            "valor": 200,
            "status": "pago",
            "forma_pagamento": "pix",
        },
        headers=admin_headers,
    )
    assert entry.status_code == 201, entry.text
    assert entry.json()["forma_pagamento"] == "pix"
