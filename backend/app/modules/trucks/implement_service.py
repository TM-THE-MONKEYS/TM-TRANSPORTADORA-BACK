"""Truck implement service."""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.trucks.implement_repository import TruckImplementRepository
from app.modules.trucks.implement_schemas import TruckImplementCreate, TruckImplementUpdate
from app.modules.trucks.models import TruckImplement
from app.modules.trucks.repository import TruckRepository
from app.modules.users.models import User
from app.shared.enums import UserRole
from app.shared.exceptions.custom import ConflictException, ForbiddenException, NotFoundException

log = structlog.get_logger(__name__)


class TruckImplementService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._repo = TruckImplementRepository(session, tenant_id)
        self._truck_repo = TruckRepository(session, tenant_id)

    def _check_write_access(self, user: User) -> None:
        if user.role not in (UserRole.ADMIN, UserRole.OPERADOR):
            raise ForbiddenException("Acesso negado")

    async def _get_truck_or_404(self, truck_id: uuid.UUID) -> None:
        truck = await self._truck_repo.get_by_id(truck_id)
        if not truck:
            raise NotFoundException("Caminhão não encontrado")

    async def list(self, truck_id: uuid.UUID, requesting_user: User) -> list[TruckImplement]:
        from app.shared.security.resource_access import assert_catalog_read_access

        assert_catalog_read_access(requesting_user)
        await self._get_truck_or_404(truck_id)
        return await self._repo.list_by_truck(truck_id)

    async def create(
        self, truck_id: uuid.UUID, data: TruckImplementCreate, created_by: User
    ) -> TruckImplement:
        self._check_write_access(created_by)
        await self._get_truck_or_404(truck_id)
        if data.placa and await self._repo.exists_placa_for_truck(truck_id, data.placa):
            raise ConflictException("Placa de implemento já cadastrada neste caminhão")

        implement = TruckImplement(truck_id=truck_id, **data.model_dump())
        implement = await self._repo.create(implement)
        await self._session.commit()
        log.info(
            "truck_implement_created",
            truck_id=str(truck_id),
            implement_id=str(implement.id),
        )
        return implement

    async def update(
        self,
        truck_id: uuid.UUID,
        implement_id: uuid.UUID,
        data: TruckImplementUpdate,
        updated_by: User,
    ) -> TruckImplement:
        self._check_write_access(updated_by)
        implement = await self._repo.get_by_id_for_truck(implement_id, truck_id)
        if not implement:
            raise NotFoundException("Implemento não encontrado")

        updates = data.model_dump(exclude_none=True)
        new_placa = updates.get("placa")
        if new_placa and await self._repo.exists_placa_for_truck(
            truck_id, new_placa, exclude_id=implement_id
        ):
            raise ConflictException("Placa de implemento já cadastrada neste caminhão")

        for field, value in updates.items():
            setattr(implement, field, value)
        if implement.placa and not implement.identificador:
            implement.identificador = implement.placa

        implement = await self._repo.update(implement)
        await self._session.commit()
        return implement

    async def delete(
        self, truck_id: uuid.UUID, implement_id: uuid.UUID, deleted_by: User
    ) -> None:
        self._check_write_access(deleted_by)
        implement = await self._repo.get_by_id_for_truck(implement_id, truck_id)
        if not implement:
            raise NotFoundException("Implemento não encontrado")
        await self._repo.soft_delete(implement)
        await self._session.commit()
        log.info(
            "truck_implement_deleted",
            truck_id=str(truck_id),
            implement_id=str(implement_id),
        )
