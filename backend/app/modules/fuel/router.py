"""Fuel refill (abastecimento) routes."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_active_user
from app.api.v1.dependencies.database import get_db
from app.modules.fuel.schemas import (
    ActiveFreightContext,
    EligibleFreightItem,
    FuelFreightSummary,
    FuelRefillCreate,
    FuelRefillCreatedResponse,
    FuelRefillRead,
)
from app.modules.fuel.service import FuelService
from app.modules.users.models import User
from app.shared.pagination import PagedResponse, PageParams

router = APIRouter(prefix="/fuel", tags=["abastecimento"])


@router.post(
    "",
    response_model=FuelRefillCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_fuel_refill(
    payload: FuelRefillCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> FuelRefillCreatedResponse:
    """Registra abastecimento vinculado ao frete e motorista (litros + valor BR)."""
    service = FuelService(db)
    return await service.create(payload, current_user)


@router.get("/eligible-freights", response_model=list[EligibleFreightItem])
async def list_eligible_freights_for_fuel(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[EligibleFreightItem]:
    """Fretes elegíveis para abastecimento (sem concluídos/cancelados/orçamento).

    Motorista: apenas fretes em que está vinculado. Admin/operador: todos em viagem.
    """
    service = FuelService(db)
    return await service.list_eligible_freights(current_user)


@router.get("/active-freight", response_model=ActiveFreightContext)
async def get_active_freight_for_driver(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ActiveFreightContext:
    """Frete em andamento do motorista logado (pré-preenche tela de abastecimento)."""
    service = FuelService(db)
    return await service.get_active_freight_context(current_user)


@router.get("/freight/{freight_id}/summary", response_model=FuelFreightSummary)
async def get_freight_fuel_summary(
    freight_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> FuelFreightSummary:
    service = FuelService(db)
    return await service.get_freight_summary(freight_id, current_user)


@router.get("", response_model=PagedResponse[FuelRefillRead])
async def list_fuel_refills(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> PagedResponse[FuelRefillRead]:
    """Histórico geral de abastecimentos (admin/operador: todos; motorista: só os seus)."""
    service = FuelService(db)
    return await service.list_all(PageParams(page=page, size=size), current_user)


@router.get("/freight/{freight_id}", response_model=PagedResponse[FuelRefillRead])
async def list_freight_fuel_refills(
    freight_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> PagedResponse[FuelRefillRead]:
    service = FuelService(db)
    return await service.list_by_freight(freight_id, PageParams(page=page, size=size), current_user)


@router.get("/{refill_id}", response_model=FuelRefillRead)
async def get_fuel_refill(
    refill_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> FuelRefillRead:
    service = FuelService(db)
    return await service.get_by_id(refill_id, current_user)
