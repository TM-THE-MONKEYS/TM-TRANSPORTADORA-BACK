"""Driver routes."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from starlette.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_active_user
from app.api.v1.dependencies.database import get_db
from app.modules.drivers.document_schemas import DriverDocumentFrontendRead
from app.modules.drivers.document_service import DriverDocumentService
from app.modules.drivers.schemas import (
    DriverCreate,
    DriverFrontendListItem,
    DriverFrontendRead,
    DriverUpdate,
)
from app.modules.drivers.service import DriverService
from app.modules.users.models import User
from app.shared.enums import DriverDocumentType, DriverStatus
from app.shared.pagination import PagedResponse, PageParams

router = APIRouter(prefix="/drivers", tags=["drivers"])


@router.get("", response_model=PagedResponse[DriverFrontendListItem])
async def list_drivers(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    status: DriverStatus | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
) -> PagedResponse[DriverFrontendListItem]:
    service = DriverService(db, current_user.tenant_id)
    params = PageParams(page=page, size=size)
    result = await service.list(params, current_user, status, search)
    frontend_items = [DriverFrontendListItem.from_orm(d) for d in result.items]
    return PagedResponse.create(frontend_items, result.total, params)


@router.post("", response_model=DriverFrontendRead, status_code=status.HTTP_201_CREATED)
async def create_driver(
    payload: DriverCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> DriverFrontendRead:
    service = DriverService(db, current_user.tenant_id)
    result = await service.create(payload, current_user)
    return DriverFrontendRead.from_orm(
        result.driver,
        temporary_password=result.temporary_password,
    )


@router.get("/{driver_id}", response_model=DriverFrontendRead)
async def get_driver(
    driver_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> DriverFrontendRead:
    service = DriverService(db, current_user.tenant_id)
    driver = await service.get_by_id(driver_id, current_user)
    return DriverFrontendRead.from_orm(driver)


@router.patch("/{driver_id}", response_model=DriverFrontendRead)
async def update_driver(
    driver_id: uuid.UUID,
    payload: DriverUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> DriverFrontendRead:
    service = DriverService(db, current_user.tenant_id)
    driver = await service.update(driver_id, payload, current_user)
    return DriverFrontendRead.from_orm(driver)


@router.delete(
    "/{driver_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_driver(
    driver_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Response:
    service = DriverService(db, current_user.tenant_id)
    await service.delete(driver_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{driver_id}/documents", response_model=list[DriverDocumentFrontendRead])
async def list_driver_documents(
    driver_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[DriverDocumentFrontendRead]:
    service = DriverDocumentService(db, current_user.tenant_id)
    items = await service.list(driver_id, current_user)
    return [DriverDocumentFrontendRead.from_orm(d, driver_id=driver_id) for d in items]


@router.post(
    "/{driver_id}/documents",
    response_model=DriverDocumentFrontendRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_driver_document(
    driver_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    file: UploadFile = File(...),
    document_type: DriverDocumentType = Form(...),
    label: str | None = Form(default=None),
) -> DriverDocumentFrontendRead:
    content = await file.read()
    filename = file.filename or "document"
    content_type = file.content_type or "application/octet-stream"
    service = DriverDocumentService(db, current_user.tenant_id)
    document = await service.upload(
        driver_id,
        document_type=document_type,
        filename=filename,
        content_type=content_type,
        content=content,
        label=label,
        uploaded_by=current_user,
    )
    return DriverDocumentFrontendRead.from_orm(document, driver_id=driver_id)


@router.get("/{driver_id}/documents/{document_id}/file")
async def download_driver_document(
    driver_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> StreamingResponse:
    service = DriverDocumentService(db, current_user.tenant_id)
    document, data = await service.get_file(driver_id, document_id, current_user)
    return StreamingResponse(
        iter([data]),
        media_type=document.content_type,
        headers={
            "Content-Disposition": f'inline; filename="{document.nome_arquivo}"',
        },
    )


@router.delete(
    "/{driver_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_driver_document(
    driver_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Response:
    service = DriverDocumentService(db, current_user.tenant_id)
    await service.delete(driver_id, document_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
