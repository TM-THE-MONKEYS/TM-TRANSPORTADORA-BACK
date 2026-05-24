"""Controle de acesso a recursos (anti-IDOR por papel)."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.drivers.models import Driver
from app.modules.freights.models import Freight
from app.modules.users.models import User
from app.shared.enums import UserRole
from app.shared.exceptions.custom import ForbiddenException

_CATALOG_READ_ROLES = frozenset(
    {UserRole.ADMIN, UserRole.OPERADOR, UserRole.FINANCEIRO}
)
_FREIGHT_READ_ALL_ROLES = frozenset(
    {UserRole.ADMIN, UserRole.OPERADOR, UserRole.FINANCEIRO}
)


async def get_driver_id_for_user(session: AsyncSession, user: User) -> uuid.UUID | None:
    result = await session.execute(select(Driver.id).where(Driver.user_id == user.id))
    return result.scalar_one_or_none()


async def get_driver_user_id(session: AsyncSession, driver_id: uuid.UUID) -> uuid.UUID | None:
    result = await session.execute(select(Driver.user_id).where(Driver.id == driver_id))
    return result.scalar_one_or_none()


async def assert_freight_read_access(
    session: AsyncSession, freight: Freight, user: User
) -> None:
    """Motorista só acessa fretes em que está vinculado como driver_id."""
    if user.role not in _FREIGHT_READ_ALL_ROLES:
        if user.role != UserRole.MOTORISTA:
            raise ForbiddenException("Acesso negado a fretes")
        if not freight.driver_id:
            raise ForbiddenException("Acesso negado a este frete")
        driver_user_id = await get_driver_user_id(session, freight.driver_id)
        if driver_user_id != user.id:
            raise ForbiddenException("Acesso negado a este frete")


async def resolve_freight_list_driver_filter(
    session: AsyncSession,
    user: User,
    driver_id: uuid.UUID | None,
) -> uuid.UUID | None:
    """Força escopo do motorista na listagem; impede filtro por outro driver_id."""
    if user.role != UserRole.MOTORISTA:
        return driver_id

    my_driver_id = await get_driver_id_for_user(session, user)
    if not my_driver_id:
        return uuid.UUID(int=0)

    if driver_id is not None and driver_id != my_driver_id:
        raise ForbiddenException("Não é permitido consultar fretes de outro motorista")

    return my_driver_id


def assert_catalog_read_access(user: User) -> None:
    """Cadastros (clientes, motoristas, caminhões, manutenção) — motorista sem leitura."""
    if user.role not in _CATALOG_READ_ROLES:
        raise ForbiddenException("Acesso negado")
