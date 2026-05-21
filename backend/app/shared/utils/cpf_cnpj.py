"""CPF and CNPJ validation utilities."""
from __future__ import annotations

import re


def _strip(value: str) -> str:
    return re.sub(r"\D", "", value)


def validate_cpf(cpf: str) -> bool:
    cpf = _strip(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False

    def _calc_digit(digits: str, factor: int) -> int:
        total = sum(int(d) * (factor - i) for i, d in enumerate(digits))
        remainder = total % 11
        return 0 if remainder < 2 else 11 - remainder

    if int(cpf[9]) != _calc_digit(cpf[:9], 10):
        return False
    return int(cpf[10]) == _calc_digit(cpf[:10], 11)


def validate_cnpj(cnpj: str) -> bool:
    cnpj = _strip(cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False

    def _calc_digit(digits: str, weights: list[int]) -> int:
        total = sum(int(d) * w for d, w in zip(digits, weights))
        remainder = total % 11
        return 0 if remainder < 2 else 11 - remainder

    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    w2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    if int(cnpj[12]) != _calc_digit(cnpj[:12], w1):
        return False
    return int(cnpj[13]) == _calc_digit(cnpj[:13], w2)


def validate_cpf_or_cnpj(value: str) -> bool:
    clean = _strip(value)
    if len(clean) == 11:
        return validate_cpf(clean)
    if len(clean) == 14:
        return validate_cnpj(clean)
    return False


def format_cpf(cpf: str) -> str:
    cpf = _strip(cpf)
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def format_cnpj(cnpj: str) -> str:
    cnpj = _strip(cnpj)
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
