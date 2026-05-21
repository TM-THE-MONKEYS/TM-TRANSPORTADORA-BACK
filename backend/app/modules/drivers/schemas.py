"""Driver schemas."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.shared.enums import CNHCategory, DriverStatus
from app.shared.utils.cpf_cnpj import validate_cpf


class DriverCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    cpf: str = Field(min_length=11, max_length=14)
    telefone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    cnh: str = Field(min_length=9, max_length=20)
    cnh_category: CNHCategory
    cnh_expiry: date
    status: DriverStatus = DriverStatus.ATIVO
    observacoes: str | None = None
    user_id: uuid.UUID | None = None

    @field_validator("cpf")
    @classmethod
    def validate_cpf_field(cls, v: str) -> str:
        import re
        clean = re.sub(r"\D", "", v)
        if not validate_cpf(clean):
            raise ValueError("CPF inválido")
        return clean

    @field_validator("cnh_expiry")
    @classmethod
    def validate_cnh_expiry(cls, v: date) -> date:
        from datetime import date as date_type
        if v < date_type.today():
            raise ValueError("CNH vencida")
        return v


class DriverUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=150)
    telefone: str | None = None
    email: EmailStr | None = None
    cnh_category: CNHCategory | None = None
    cnh_expiry: date | None = None
    status: DriverStatus | None = None
    observacoes: str | None = None


class DriverRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    nome: str
    cpf: str
    telefone: str | None
    email: str | None
    cnh: str
    cnh_category: CNHCategory
    cnh_expiry: date
    status: DriverStatus
    observacoes: str | None
    created_at: datetime
    updated_at: datetime


class DriverListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    cpf: str
    cnh: str
    cnh_category: CNHCategory
    cnh_expiry: date
    status: DriverStatus
    created_at: datetime


# ── Frontend-compatible schemas (English field names) ────────────────────────

class DriverFrontendRead(BaseModel):
    """Maps backend Portuguese field names to English names expected by the frontend."""

    id: uuid.UUID
    tenant_id: str = "default"
    name: str
    cpf: str | None = None
    cnh_number: str
    cnh_category: str
    cnh_expires_at: str  # ISO date string
    status: DriverStatus
    phone: str | None = None
    photo_url: str | None = None
    commission_pct: float | None = None
    created_at: str

    @classmethod
    def from_orm(cls, driver: object) -> "DriverFrontendRead":
        return cls(
            id=driver.id,  # type: ignore[attr-defined]
            name=driver.nome,  # type: ignore[attr-defined]
            cpf=driver.cpf,  # type: ignore[attr-defined]
            cnh_number=driver.cnh,  # type: ignore[attr-defined]
            cnh_category=driver.cnh_category,  # type: ignore[attr-defined]
            cnh_expires_at=driver.cnh_expiry.isoformat(),  # type: ignore[attr-defined]
            status=driver.status,  # type: ignore[attr-defined]
            phone=driver.telefone,  # type: ignore[attr-defined]
            created_at=driver.created_at.isoformat(),  # type: ignore[attr-defined]
        )


class DriverFrontendListItem(BaseModel):
    id: uuid.UUID
    tenant_id: str = "default"
    name: str
    cpf: str | None = None
    cnh_number: str
    cnh_category: str
    cnh_expires_at: str
    status: DriverStatus
    created_at: str

    @classmethod
    def from_orm(cls, driver: object) -> "DriverFrontendListItem":
        return cls(
            id=driver.id,  # type: ignore[attr-defined]
            name=driver.nome,  # type: ignore[attr-defined]
            cpf=driver.cpf,  # type: ignore[attr-defined]
            cnh_number=driver.cnh,  # type: ignore[attr-defined]
            cnh_category=driver.cnh_category,  # type: ignore[attr-defined]
            cnh_expires_at=driver.cnh_expiry.isoformat(),  # type: ignore[attr-defined]
            status=driver.status,  # type: ignore[attr-defined]
            created_at=driver.created_at.isoformat(),  # type: ignore[attr-defined]
        )
