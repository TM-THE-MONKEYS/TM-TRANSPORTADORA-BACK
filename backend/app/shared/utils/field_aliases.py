"""Map English frontend field names to backend Portuguese names."""
from __future__ import annotations

from typing import Any

from app.shared.utils.data_normalization import (
    ADDRESS_RULES,
    apply_field_rules,
)

# Fields sent by the frontend but not accepted on create/update
IGNORED_FRONTEND_FIELDS = frozenset({
    "id",
    "tenant_id",
    "branch_id",
    "created_at",
    "updated_at",
    "photo_url",
    "commission_pct",
    "customer_name",
    "code",
})


def map_fields(data: Any, mapping: dict[str, str]) -> Any:
    if not isinstance(data, dict):
        return data
    normalized = dict(data)
    for frontend_key, backend_key in mapping.items():
        if frontend_key in normalized and backend_key not in normalized:
            normalized[backend_key] = normalized[frontend_key]
    return normalized


def strip_ignored_fields(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if k not in IGNORED_FRONTEND_FIELDS}


def normalize_date_field(data: dict[str, Any], field: str) -> None:
    """Accept ISO datetime strings from the frontend (e.g. 2027-12-31T00:00:00.000Z)."""
    value = data.get(field)
    if isinstance(value, str) and "T" in value:
        data[field] = value.split("T")[0]


def require_non_empty_string(
    data: dict[str, Any], field: str, label: str
) -> None:
    value = data.get(field)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError(f"{label} é obrigatório")


def drop_null_optionals(data: dict[str, Any], fields: tuple[str, ...]) -> None:
    for field in fields:
        if data.get(field) is None:
            data.pop(field, None)


def normalize_create_payload(
    data: object,
    mapping: dict[str, str],
    required: tuple[tuple[str, str], ...],
    optional_nullable: tuple[str, ...] = (),
    *,
    field_rules: dict[str, Any] | None = None,
    nested_rules: dict[str, dict[str, Any]] | None = None,
) -> object:
    if not isinstance(data, dict):
        return data
    normalized = strip_ignored_fields(map_fields(data, mapping))
    drop_null_optionals(normalized, optional_nullable)
    for field, label in required:
        require_non_empty_string(normalized, field, label)
    if field_rules:
        apply_field_rules(normalized, field_rules, nested=nested_rules)
    return normalized


def normalize_update_payload(
    data: object,
    mapping: dict[str, str],
    *,
    field_rules: dict[str, Any] | None = None,
    nested_rules: dict[str, dict[str, Any]] | None = None,
) -> object:
    if not isinstance(data, dict):
        return data
    normalized = strip_ignored_fields(map_fields(data, mapping))
    if field_rules:
        apply_field_rules(normalized, field_rules, nested=nested_rules)
    return normalized


DRIVER_CREATE_ALIASES = {
    "name": "nome",
    "phone": "telefone",
    "cnh_number": "cnh",
    "cnh_expires_at": "cnh_expiry",
    "senha": "password",
}

DRIVER_UPDATE_ALIASES = {
    "name": "nome",
    "phone": "telefone",
    "cnh_expires_at": "cnh_expiry",
}

TRUCK_CREATE_ALIASES = {
    "plate": "placa",
    "brand": "marca",
    "model": "modelo",
    "year": "ano",
    "capacity_kg": "capacidade_kg",
    "avg_consumption_km_l": "consumo_km_l",
    "mileage_km": "km_atual",
}

TRUCK_UPDATE_ALIASES = {
    "brand": "marca",
    "model": "modelo",
    "capacity_kg": "capacidade_kg",
    "avg_consumption_km_l": "consumo_km_l",
    "mileage_km": "km_atual",
}
