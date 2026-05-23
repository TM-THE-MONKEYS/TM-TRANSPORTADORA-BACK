"""Client schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.shared.utils.cpf_cnpj import validate_cpf_or_cnpj
from app.shared.utils.data_normalization import (
    ADDRESS_RULES,
    CLIENT_CREATE_RULES,
    CLIENT_UPDATE_RULES,
    apply_field_rules,
)
from app.shared.utils.field_aliases import normalize_create_payload, normalize_update_payload


class AddressSchema(BaseModel):
    logradouro: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    estado: str | None = Field(default=None, max_length=2)
    cep: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_address(cls, data: object) -> object:
        if isinstance(data, dict):
            apply_field_rules(data, ADDRESS_RULES)
        return data


class ClientCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=200)
    cpf_cnpj: str = Field(min_length=11, max_length=18)
    email: EmailStr | None = None
    telefone: str | None = Field(default=None, max_length=20)
    endereco: AddressSchema | None = None
    observacoes: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, data: object) -> object:
        return normalize_create_payload(
            data,
            {},
            required=(("nome", "Nome"), ("cpf_cnpj", "CPF/CNPJ")),
            optional_nullable=("email", "telefone", "endereco", "observacoes"),
            field_rules=CLIENT_CREATE_RULES,
            nested_rules={"endereco": ADDRESS_RULES},
        )

    @field_validator("cpf_cnpj")
    @classmethod
    def validate_doc(cls, v: str) -> str:
        if not validate_cpf_or_cnpj(v):
            raise ValueError("CPF ou CNPJ inválido")
        return v


class ClientUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=200)
    email: EmailStr | None = None
    telefone: str | None = None
    endereco: AddressSchema | None = None
    observacoes: str | None = None
    is_active: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, data: object) -> object:
        return normalize_update_payload(
            data,
            {},
            field_rules=CLIENT_UPDATE_RULES,
            nested_rules={"endereco": ADDRESS_RULES},
        )


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
