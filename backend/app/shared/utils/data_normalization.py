"""Padronização de dados de entrada (maiúsculas, números BR, documentos)."""
from __future__ import annotations

import re
from typing import Any, Literal

NormType = Literal[
    "upper",
    "lower",
    "digits",
    "plate",
    "upper_alnum",
    "decimal",
    "integer",
    "uf",
]

_WHITESPACE_RE = re.compile(r"\s+")


def collapse_spaces(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value.strip())


def normalize_upper_text(value: Any) -> str | Any:
    if value is None or not isinstance(value, str):
        return value
    return collapse_spaces(value).upper()


def normalize_lower_text(value: Any) -> str | Any:
    if value is None or not isinstance(value, str):
        return value
    return collapse_spaces(value).lower()


def normalize_digits(value: Any) -> str | Any:
    if value is None:
        return value
    if isinstance(value, (int, float)):
        return str(int(value)) if float(value).is_integer() else re.sub(r"\D", "", str(value))
    if not isinstance(value, str):
        return value
    return re.sub(r"\D", "", value)


def normalize_plate(value: Any) -> str | Any:
    if value is None or not isinstance(value, str):
        return value
    return re.sub(r"[^A-Za-z0-9]", "", value).upper()


def normalize_upper_alnum(value: Any) -> str | Any:
    if value is None or not isinstance(value, str):
        return value
    return re.sub(r"[^A-Za-z0-9]", "", value).upper()


def normalize_uf(value: Any) -> str | Any:
    if value is None or not isinstance(value, str):
        return value
    clean = re.sub(r"[^A-Za-z]", "", value).upper()
    return clean[:2] if clean else value


def parse_decimal_br(value: Any) -> float | Any:
    """Converte formatos BR/US: 30.000,50 | 30000,50 | 30000.50 | 30,000.50."""
    if value is None:
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return value

    raw = value.strip().replace(" ", "")
    if not raw:
        raise ValueError("Valor numérico inválido")

    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            # 1.234,56
            raw = raw.replace(".", "").replace(",", ".")
        else:
            # 1,234.56
            raw = raw.replace(",", "")
    elif "," in raw:
        parts = raw.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            raw = parts[0].replace(".", "") + "." + parts[1]
        else:
            raw = raw.replace(",", "")
    elif raw.count(".") > 1:
        raw = raw.replace(".", "")
    elif "." in raw:
        integer, fractional = raw.rsplit(".", 1)
        if len(fractional) == 3 and integer.isdigit():
            raw = raw.replace(".", "")

    return float(raw)


def parse_integer_br(value: Any) -> int | Any:
    if value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        decimal = parse_decimal_br(value)
        if isinstance(decimal, float):
            return int(decimal)
    return value


def _apply_rule(value: Any, rule: NormType) -> Any:
    if rule == "upper":
        return normalize_upper_text(value)
    if rule == "lower":
        return normalize_lower_text(value)
    if rule == "digits":
        return normalize_digits(value)
    if rule == "plate":
        return normalize_plate(value)
    if rule == "upper_alnum":
        return normalize_upper_alnum(value)
    if rule == "decimal":
        return parse_decimal_br(value)
    if rule == "integer":
        return parse_integer_br(value)
    if rule == "uf":
        return normalize_uf(value)
    return value


def apply_field_rules(
    data: dict[str, Any],
    rules: dict[str, NormType],
    *,
    nested: dict[str, dict[str, NormType]] | None = None,
) -> dict[str, Any]:
    """Aplica regras de normalização em campos do payload (in-place)."""
    for field, rule in rules.items():
        if field in data and data[field] is not None:
            data[field] = _apply_rule(data[field], rule)

    if nested:
        for nested_field, nested_rules in nested.items():
            child = data.get(nested_field)
            if isinstance(child, dict):
                apply_field_rules(child, nested_rules)

    return data


# ── Regras por domínio ───────────────────────────────────────────────────────

ADDRESS_RULES: dict[str, NormType] = {
    "logradouro": "upper",
    "numero": "upper",
    "complemento": "upper",
    "bairro": "upper",
    "cidade": "upper",
    "estado": "uf",
    "cep": "digits",
}

DRIVER_CREATE_RULES: dict[str, NormType] = {
    "nome": "upper",
    "cpf": "digits",
    "telefone": "digits",
    "cnh": "digits",
    "cnh_category": "upper",
    "email": "lower",
    "observacoes": "upper",
}

DRIVER_UPDATE_RULES: dict[str, NormType] = {
    "nome": "upper",
    "telefone": "digits",
    "email": "lower",
    "observacoes": "upper",
}

TRUCK_CREATE_RULES: dict[str, NormType] = {
    "placa": "plate",
    "modelo": "upper",
    "marca": "upper",
    "ano": "integer",
    "capacidade_kg": "decimal",
    "consumo_km_l": "decimal",
    "km_atual": "decimal",
    "renavam": "digits",
    "chassi": "upper_alnum",
    "cor": "upper",
    "observacoes": "upper",
}

TRUCK_UPDATE_RULES: dict[str, NormType] = {
    "modelo": "upper",
    "marca": "upper",
    "capacidade_kg": "decimal",
    "consumo_km_l": "decimal",
    "km_atual": "decimal",
    "cor": "upper",
    "observacoes": "upper",
}

IMPLEMENT_CREATE_RULES: dict[str, NormType] = {
    "nome": "upper",
    "placa": "plate",
    "identificador": "upper_alnum",
    "marca": "upper",
    "modelo": "upper",
    "capacidade_kg": "decimal",
}

IMPLEMENT_UPDATE_RULES: dict[str, NormType] = {
    "nome": "upper",
    "placa": "plate",
    "identificador": "upper_alnum",
    "marca": "upper",
    "modelo": "upper",
    "capacidade_kg": "decimal",
}

CLIENT_CREATE_RULES: dict[str, NormType] = {
    "nome": "upper",
    "cpf_cnpj": "digits",
    "telefone": "digits",
    "email": "lower",
    "observacoes": "upper",
}

CLIENT_UPDATE_RULES: dict[str, NormType] = {
    "nome": "upper",
    "telefone": "digits",
    "email": "lower",
    "observacoes": "upper",
}

FREIGHT_CREATE_RULES: dict[str, NormType] = {
    "valor_frete": "decimal",
    "distancia_km": "decimal",
    "observacoes": "upper",
}

FREIGHT_UPDATE_RULES: dict[str, NormType] = {
    "valor_frete": "decimal",
    "distancia_km": "decimal",
    "observacoes": "upper",
}

FREIGHT_COST_RULES: dict[str, NormType] = {
    "tipo": "upper",
    "valor": "decimal",
    "descricao": "upper",
}

FINANCE_CREATE_RULES: dict[str, NormType] = {
    "categoria": "upper",
    "descricao": "upper",
    "valor": "decimal",
    "observacoes": "upper",
}

FINANCE_UPDATE_RULES: dict[str, NormType] = {
    "categoria": "upper",
    "descricao": "upper",
    "valor": "decimal",
    "observacoes": "upper",
}

USER_CREATE_RULES: dict[str, NormType] = {
    "nome": "upper",
    "email": "lower",
}

USER_UPDATE_RULES: dict[str, NormType] = {
    "nome": "upper",
    "email": "lower",
}

FUEL_CREATE_RULES: dict[str, NormType] = {
    "posto": "upper",
    "cidade": "upper",
    "estado": "uf",
    "observacoes": "upper",
    "valor_total": "decimal",
    "valor_litro": "decimal",
    "litros": "decimal",
    "km_atual": "decimal",
}

TOLL_CREATE_RULES: dict[str, NormType] = {
    "praca": "upper",
    "rodovia": "upper",
    "cidade": "upper",
    "estado": "uf",
    "observacoes": "upper",
    "valor": "decimal",
    "quantidade": "integer",
}
