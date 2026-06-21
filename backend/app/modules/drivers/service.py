"""Driver service."""
from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.password import hash_password
from app.modules.drivers.models import Driver
from app.modules.drivers.repository import DriverRepository
from app.modules.drivers.schemas import DriverCreate, DriverUpdate
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.shared.enums import DriverStatus, UserRole
from app.shared.exceptions.custom import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.shared.pagination import PagedResponse, PageParams
from app.shared.security.resource_access import assert_catalog_read_access

log = structlog.get_logger(__name__)


def _generate_temporary_password() -> str:
    """Gera senha temporária segura quando o frontend não envia password."""
    return secrets.token_urlsafe(16)


@dataclass
class DriverCreateResult:
    driver: Driver
    temporary_password: str | None = None


class DriverService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._repo = DriverRepository(session, tenant_id)
        self._user_repo = UserRepository(session, tenant_id)

    def _check_write_access(self, user: User) -> None:
        if user.role not in (UserRole.ADMIN, UserRole.OPERADOR):
            raise ForbiddenException("Acesso negado")

    async def create(self, data: DriverCreate, created_by: User) -> DriverCreateResult:
        self._check_write_access(created_by)
        if await self._repo.exists_by_cpf(data.cpf):
            raise ConflictException("CPF já cadastrado")
        if await self._repo.exists_by_cnh(data.cnh):
            raise ConflictException("CNH já cadastrada")

        driver_email = (data.email or f"{data.cpf}@motorista.local").lower()
        if await self._user_repo.exists_by_email_global(driver_email):
            raise ConflictException("Email já cadastrado para outro usuário")

        temporary_password: str | None = None
        if data.password:
            password = data.password
        else:
            password = _generate_temporary_password()
            temporary_password = password

        driver_user = User(
            nome=data.nome,
            email=driver_email,
            hashed_password=hash_password(password),
            role=UserRole.MOTORISTA,
            is_active=True,
            tenant_id=self._tenant_id,
        )
        self._session.add(driver_user)
        await self._session.flush()
        await self._session.refresh(driver_user)

        driver_data = data.model_dump(exclude={"password"})
        driver_data["user_id"] = driver_user.id
        driver_data["email"] = data.email
        driver = Driver(**driver_data)
        driver = await self._repo.create(driver)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            message = str(exc.__cause__ or exc).lower()
            if "cpf" in message:
                raise ConflictException("CPF já cadastrado") from exc
            if "cnh" in message:
                raise ConflictException("CNH já cadastrada") from exc
            if "email" in message:
                raise ConflictException("Email já cadastrado para outro usuário") from exc
            raise
        log.info(
            "driver_created_with_account",
            driver_id=str(driver.id),
            user_id=str(driver_user.id),
            temporary_password_issued=temporary_password is not None,
        )
        return DriverCreateResult(driver=driver, temporary_password=temporary_password)

    async def get_by_id(self, driver_id: uuid.UUID, requesting_user: User) -> Driver:
        assert_catalog_read_access(requesting_user)
        driver = await self._repo.get_by_id(driver_id)
        if not driver:
            raise NotFoundException("Motorista não encontrado")
        return driver

    async def list(
        self,
        params: PageParams,
        requesting_user: User,
        status: DriverStatus | None = None,
        search: str | None = None,
    ) -> PagedResponse[Driver]:
        assert_catalog_read_access(requesting_user)
        items, total = await self._repo.list(params, status, search)
        return PagedResponse.create(items, total, params)

    async def update(self, driver_id: uuid.UUID, data: DriverUpdate, updated_by: User) -> Driver:
        self._check_write_access(updated_by)
        driver = await self.get_by_id(driver_id, updated_by)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(driver, field, value)
        driver = await self._repo.update(driver)
        await self._session.commit()
        return driver

    async def delete(self, driver_id: uuid.UUID, deleted_by: User) -> None:
        self._check_write_access(deleted_by)
        driver = await self.get_by_id(driver_id, deleted_by)
        user_id = driver.user_id
        await self._repo.hard_delete(driver)
        if user_id:
            linked_user = await self._user_repo.get_by_id(user_id)
            if linked_user:
                await self._session.delete(linked_user)
        await self._session.commit()
        log.info(
            "driver_deleted",
            driver_id=str(driver_id),
            user_id=str(user_id) if user_id else None,
        )
