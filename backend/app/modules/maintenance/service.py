"""Maintenance service."""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.maintenance.models import Maintenance
from app.modules.maintenance.repository import MaintenanceRepository
from app.modules.maintenance.schemas import MaintenanceCreate, MaintenanceUpdate
from app.modules.users.models import User
from app.shared.enums import MaintenanceStatus, MaintenanceType, UserRole
from app.shared.exceptions.custom import ForbiddenException, NotFoundException
from app.shared.pagination import PagedResponse, PageParams
from app.shared.security.resource_access import assert_catalog_read_access

log = structlog.get_logger(__name__)


class MaintenanceService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = MaintenanceRepository(session)

    def _check_write_access(self, user: User) -> None:
        if user.role not in (UserRole.ADMIN, UserRole.OPERADOR):
            raise ForbiddenException("Acesso negado")

    async def create(self, data: MaintenanceCreate, created_by: User) -> Maintenance:
        self._check_write_access(created_by)
        maintenance = Maintenance(**data.model_dump())
        maintenance = await self._repo.create(maintenance)
        await self._session.commit()
        log.info("maintenance_created", maintenance_id=str(maintenance.id), truck_id=str(data.truck_id))
        return maintenance

    async def get_by_id(self, maintenance_id: uuid.UUID, requesting_user: User) -> Maintenance:
        assert_catalog_read_access(requesting_user)
        maintenance = await self._repo.get_by_id(maintenance_id)
        if not maintenance:
            raise NotFoundException("Manutenção não encontrada")
        return maintenance

    async def list(
        self,
        params: PageParams,
        requesting_user: User,
        truck_id: uuid.UUID | None = None,
        status: MaintenanceStatus | None = None,
        tipo: MaintenanceType | None = None,
    ) -> PagedResponse[Maintenance]:
        assert_catalog_read_access(requesting_user)
        items, total = await self._repo.list(params, truck_id, status, tipo)
        return PagedResponse.create(items, total, params)

    async def update(self, maintenance_id: uuid.UUID, data: MaintenanceUpdate, updated_by: User) -> Maintenance:
        self._check_write_access(updated_by)
        maintenance = await self.get_by_id(maintenance_id, updated_by)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(maintenance, field, value)
        maintenance = await self._repo.update(maintenance)
        await self._session.commit()
        return maintenance

    async def delete(self, maintenance_id: uuid.UUID, deleted_by: User) -> None:
        self._check_write_access(deleted_by)
        maintenance = await self.get_by_id(maintenance_id, deleted_by)
        await self._repo.soft_delete(maintenance)
        await self._session.commit()

    async def get_alerts(self, days_ahead: int, requesting_user: User) -> list[Maintenance]:
        assert_catalog_read_access(requesting_user)
        return await self._repo.get_upcoming_alerts(days_ahead)
