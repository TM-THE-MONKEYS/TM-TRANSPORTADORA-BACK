"""Driver document service."""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.modules.drivers.document_repository import DriverDocumentRepository
from app.modules.drivers.models import DriverDocument
from app.modules.drivers.repository import DriverRepository
from app.modules.users.models import User
from app.shared.enums import DriverDocumentType, UserRole
from app.shared.exceptions.custom import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)
from app.shared.security.resource_access import assert_catalog_read_access
from app.shared.storage.local_files import (
    ALLOWED_DRIVER_DOCUMENT_TYPES,
    delete_storage_file,
    normalize_driver_document_content_type,
    resolve_storage_path,
    save_driver_document_bytes,
)

log = structlog.get_logger(__name__)


class DriverDocumentService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._repo = DriverDocumentRepository(session, tenant_id)
        self._driver_repo = DriverRepository(session, tenant_id)

    def _check_write_access(self, user: User) -> None:
        if user.role not in (UserRole.ADMIN, UserRole.OPERADOR):
            raise ForbiddenException("Acesso negado")

    async def _get_driver_or_404(self, driver_id: uuid.UUID) -> None:
        driver = await self._driver_repo.get_by_id(driver_id)
        if not driver:
            raise NotFoundException("Motorista não encontrado")

    async def list(self, driver_id: uuid.UUID, requesting_user: User) -> list[DriverDocument]:
        assert_catalog_read_access(requesting_user)
        await self._get_driver_or_404(driver_id)
        return await self._repo.list_by_driver(driver_id)

    async def upload(
        self,
        driver_id: uuid.UUID,
        *,
        document_type: DriverDocumentType,
        filename: str,
        content_type: str,
        content: bytes,
        label: str | None,
        uploaded_by: User,
    ) -> DriverDocument:
        self._check_write_access(uploaded_by)
        await self._get_driver_or_404(driver_id)

        settings = get_settings()
        if len(content) > settings.upload_max_bytes:
            raise BadRequestException(
                f"Arquivo excede o limite de {settings.upload_max_bytes // (1024 * 1024)} MB"
            )
        content_type = normalize_driver_document_content_type(content_type, filename)
        if content_type not in ALLOWED_DRIVER_DOCUMENT_TYPES:
            raise BadRequestException(
                "Tipo de arquivo não permitido. Use JPG, PNG, WEBP ou PDF."
            )

        storage_key = save_driver_document_bytes(
            self._tenant_id, driver_id, filename, content
        )

        document = DriverDocument(
            driver_id=driver_id,
            tipo=document_type.value,
            titulo=label,
            nome_arquivo=filename,
            content_type=content_type,
            tamanho_bytes=len(content),
            storage_path=storage_key,
        )
        document = await self._repo.create(document)

        if document_type == DriverDocumentType.PHOTO:
            driver = await self._driver_repo.get_by_id(driver_id)
            if driver:
                driver.foto_url = f"/api/v1/drivers/{driver_id}/documents/{document.id}/file"
                await self._driver_repo.update(driver)

        await self._session.commit()
        log.info(
            "driver_document_uploaded",
            driver_id=str(driver_id),
            document_id=str(document.id),
            tipo=document_type.value,
        )
        return document

    async def get_file(
        self, driver_id: uuid.UUID, document_id: uuid.UUID, requesting_user: User
    ) -> tuple[DriverDocument, bytes]:
        assert_catalog_read_access(requesting_user)
        document = await self._repo.get_for_driver(document_id, driver_id)
        if not document:
            raise NotFoundException("Documento não encontrado")
        path = resolve_storage_path(document.storage_path)
        if not path.is_file():
            raise NotFoundException("Arquivo não encontrado no storage")
        return document, path.read_bytes()

    async def delete(
        self, driver_id: uuid.UUID, document_id: uuid.UUID, deleted_by: User
    ) -> None:
        self._check_write_access(deleted_by)
        document = await self._repo.get_for_driver(document_id, driver_id)
        if not document:
            raise NotFoundException("Documento não encontrado")
        delete_storage_file(document.storage_path)
        await self._repo.soft_delete(document)

        driver = await self._driver_repo.get_by_id(driver_id)
        if driver and driver.foto_url and str(document_id) in (driver.foto_url or ""):
            driver.foto_url = None
            await self._driver_repo.update(driver)

        await self._session.commit()
        log.info(
            "driver_document_deleted",
            driver_id=str(driver_id),
            document_id=str(document_id),
        )
