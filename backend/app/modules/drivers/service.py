"""Driver service."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.password import hash_password
from app.modules.auth.repository import RefreshTokenRepository
from app.modules.drivers.models import Driver
from app.modules.drivers.repository import DriverRepository
from app.modules.drivers.schemas import (
    DriverAccountCreate,
    DriverCreate,
    DriverResetPassword,
    DriverUpdate,
)
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
        self._token_repo = RefreshTokenRepository(session, tenant_id)

    def _check_write_access(self, user: User) -> None:
        if user.role not in (UserRole.ADMIN, UserRole.OPERADOR):
            raise ForbiddenException("Acesso negado")

    def _check_admin_access(self, user: User) -> None:
        if user.role != UserRole.ADMIN:
            raise ForbiddenException(
                "Apenas admins podem gerenciar contas de motorista"
            )

    async def create(self, data: DriverCreate, created_by: User) -> DriverCreateResult:
        self._check_write_access(created_by)
        if await self._repo.exists_by_cpf(data.cpf):
            raise ConflictException("CPF já cadastrado")
        if await self._repo.exists_by_cnh(data.cnh):
            raise ConflictException("CNH já cadastrada")

        driver = Driver(**data.model_dump())
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
            raise
        log.info("driver_created", driver_id=str(driver.id), user_id=None)
        return DriverCreateResult(driver=driver, temporary_password=None)

    async def create_account(
        self,
        driver_id: uuid.UUID,
        data: DriverAccountCreate,
        created_by: User,
    ) -> DriverCreateResult:
        self._check_admin_access(created_by)
        driver = await self._repo.get_by_id(driver_id)
        if not driver:
            raise NotFoundException("Motorista não encontrado")
        if driver.user_id is not None:
            raise ConflictException("Motorista já possui conta de acesso")

        email = data.email.lower()
        if await self._user_repo.exists_by_email_global(email):
            raise ConflictException("Email já cadastrado para outro usuário")

        driver_user = User(
            nome=driver.nome,
            email=email,
            hashed_password=hash_password(data.password),
            role=UserRole.MOTORISTA,
            is_active=True,
            tenant_id=self._tenant_id,
        )
        self._session.add(driver_user)
        await self._session.flush()
        await self._session.refresh(driver_user)

        driver.user_id = driver_user.id
        driver.email = email
        driver = await self._repo.update(driver)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            message = str(exc.__cause__ or exc).lower()
            if "email" in message:
                raise ConflictException(
                    "Email já cadastrado para outro usuário"
                ) from exc
            if "user_id" in message:
                raise ConflictException(
                    "Motorista já possui conta de acesso"
                ) from exc
            raise
        log.info(
            "driver_account_created",
            driver_id=str(driver.id),
            user_id=str(driver_user.id),
            temporary_password_issued=True,
        )
        return DriverCreateResult(driver=driver, temporary_password=data.password)

    async def reset_password(
        self,
        driver_id: uuid.UUID,
        data: DriverResetPassword,
        reset_by: User,
    ) -> None:
        self._check_admin_access(reset_by)
        driver = await self._repo.get_by_id(driver_id)
        if not driver:
            raise NotFoundException("Motorista não encontrado")
        if not driver.user_id:
            raise NotFoundException("Motorista não possui conta de acesso")

        linked_user = await self._user_repo.get_by_id(driver.user_id)
        if not linked_user:
            raise NotFoundException("Motorista não possui conta de acesso")

        linked_user.hashed_password = hash_password(data.password)
        await self._token_repo.revoke_all_for_user(linked_user.id)
        await self._session.commit()
        log.info(
            "driver_password_reset",
            driver_id=str(driver_id),
            user_id=str(linked_user.id),
        )

    async def delete_account(
        self,
        driver_id: uuid.UUID,
        deleted_by: User,
    ) -> None:
        """Unlink and remove login User; keep Driver record."""
        self._check_admin_access(deleted_by)
        driver = await self._repo.get_by_id(driver_id)
        if not driver:
            raise NotFoundException("Motorista não encontrado")
        if not driver.user_id:
            raise NotFoundException("Motorista não possui conta de acesso")

        linked_user = await self._user_repo.get_by_id(driver.user_id)
        if not linked_user:
            driver.user_id = None
            await self._repo.update(driver)
            await self._session.commit()
            raise NotFoundException("Motorista não possui conta de acesso")

        user_id = linked_user.id
        await self._token_repo.revoke_all_for_user(user_id)

        driver.user_id = None
        driver.email = None
        await self._repo.update(driver)

        # Hard-delete: tm_users.email is UNIQUE even after soft-delete,
        # so reuse of login email on recreate requires row removal.
        await self._session.delete(linked_user)
        await self._session.commit()
        log.info(
            "driver_account_deleted",
            driver_id=str(driver_id),
            user_id=str(user_id),
        )

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
        competencia_mes: int | None = None,
        competencia_ano: int | None = None,
        truck_id: uuid.UUID | None = None,
    ) -> PagedResponse[Driver]:
        assert_catalog_read_access(requesting_user)
        items, total = await self._repo.list(
            params,
            status,
            search,
            competencia_mes=competencia_mes,
            competencia_ano=competencia_ano,
            truck_id=truck_id,
        )
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
        if user_id:
            await self._token_repo.revoke_all_for_user(user_id)
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
