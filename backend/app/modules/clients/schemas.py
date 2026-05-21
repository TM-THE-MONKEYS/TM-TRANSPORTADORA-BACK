"""Client schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.shared.utils.cpf_cnpj import validate_cpf_or_cnpj


class AddressSchema(BaseModel):
    logradouro: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    estado: str | None = Field(default=None, max_length=2)
    cep: str | None = None


class ClientCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=200)
    cpf_cnpj: str = Field(min_length=11, max_length=18)
    email: EmailStr | None = None
    telefone: str | None = Field(default=None, max_length=20)
    endereco: AddressSchema | None = None
    observacoes: str | None = None

    @field_validator("cpf_cnpj")
    @classmethod
    def validate_doc(cls, v: str) -> str:
        import re
        clean = re.sub(r"\D", "", v)
        if not validate_cpf_or_cnpj(clean):
            raise ValueError("CPF ou CNPJ inválido")
        return clean


class ClientUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=200)
    email: EmailStr | None = None
    telefone: str | None = None
    endereco: AddressSchema | None = None
    observacoes: str | None = None
    is_active: bool | None = None


class ClientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    cpf_cnpj: str
    email: str | None
    telefone: str | None
    endereco: dict | None
    observacoes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ClientListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    cpf_cnpj: str
    email: str | None
    telefone: str | None
    is_active: bool
    created_at: datetime
