"""Toll charge (pedágio) routes."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_active_user
from app.api.v1.dependencies.database import get_db
from app.modules.tolls.schemas import (
    ActiveFreightContext,
    EligibleFreightItem,
    TollChargeCreate,
    TollChargeCreatedResponse,
    TollChargeRead,
    TollFreightSummary,
)
from app.modules.tolls.service import TollService
from app.modules.users.models import User
from app.shared.pagination import PagedResponse, PageParams

router = APIRouter(prefix="/tolls", tags=["pedágios"])


@router.post(
    "",
    response_model=TollChargeCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_toll_charge(
    payload: TollChargeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TollChargeCreatedResponse:
    """Registra pedágio vinculado ao frete e motorista (admin, operador ou motorista do frete)."""
    service = TollService(db, current_user.tenant_id)
    return await service.create(payload, current_user)


@router.get("/eligible-freights", response_model=list[EligibleFreightItem])
async def list_eligible_freights_for_toll(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[EligibleFreightItem]:
    """Fretes elegíveis para registro de pedágio (sem concluídos/cancelados/orçamento).

    Motorista: apenas fretes em que está vinculado. Admin/operador: todos em viagem.
    """
    service = TollService(db, current_user.tenant_id)
    return await service.list_eligible_freights(current_user)


@router.get("/active-freight", response_model=ActiveFreightContext)
async def get_active_freight_for_driver(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ActiveFreightContext:
    """Frete em andamento do motorista logado (pré-preenche tela de pedágio)."""
    service = TollService(db, current_user.tenant_id)
    return await service.get_active_freight_context(current_user)


@router.get("/freight/{freight_id}/summary", response_model=TollFreightSummary)
async def get_freight_toll_summary(
    freight_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TollFreightSummary:
    """Resumo de pedágios de um frete: valor total, quantidade total e número de registros."""
    service = TollService(db, current_user.tenant_id)
    return await service.get_freight_summary(freight_id, current_user)


@router.get("", response_model=PagedResponse[TollChargeRead])
async def list_toll_charges(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> PagedResponse[TollChargeRead]:
    """Histórico geral de pedágios (admin/operador: todos; motorista: só os seus)."""
    service = TollService(db, current_user.tenant_id)
    return await service.list_all(PageParams(page=page, size=size), current_user)


@router.get("/freight/{freight_id}", response_model=PagedResponse[TollChargeRead])
async def list_freight_toll_charges(
    freight_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> PagedResponse[TollChargeRead]:
    """Lista pedágios de um frete específico."""
    service = TollService(db, current_user.tenant_id)
    return await service.list_by_freight(freight_id, PageParams(page=page, size=size), current_user)


@router.get("/{charge_id}", response_model=TollChargeRead)
async def get_toll_charge(
    charge_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TollChargeRead:
    """Busca um registro de pedágio por ID."""
    service = TollService(db, current_user.tenant_id)
    return await service.get_by_id(charge_id, current_user)
