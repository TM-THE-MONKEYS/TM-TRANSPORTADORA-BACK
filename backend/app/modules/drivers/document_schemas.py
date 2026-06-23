"""Driver document schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.shared.enums import DriverDocumentType


class DriverDocumentFrontendRead(BaseModel):
    id: uuid.UUID
    driver_id: uuid.UUID
    type: str
    label: str | None = None
    filename: str
    content_type: str
    file_size: int
    download_path: str
    created_at: str

    @classmethod
    def from_orm(cls, doc: object, *, driver_id: uuid.UUID) -> "DriverDocumentFrontendRead":
        doc_id = doc.id  # type: ignore[attr-defined]
        return cls(
            id=doc_id,
            driver_id=driver_id,
            type=doc.tipo,  # type: ignore[attr-defined]
            label=doc.titulo,  # type: ignore[attr-defined]
            filename=doc.nome_arquivo,  # type: ignore[attr-defined]
            content_type=doc.content_type,  # type: ignore[attr-defined]
            file_size=doc.tamanho_bytes,  # type: ignore[attr-defined]
            download_path=f"/drivers/{driver_id}/documents/{doc_id}/file",
            created_at=doc.created_at.isoformat(),  # type: ignore[attr-defined]
        )


class DriverDocumentCreateForm(BaseModel):
    document_type: DriverDocumentType
    label: str | None = Field(default=None, max_length=150)
