"""Unit tests for shared utilities."""
from __future__ import annotations

from datetime import date

import pytest

from app.shared.exceptions.custom import BadRequestException
from app.shared.filters.competencia import (
    is_competencia_within_limit,
    resolve_competencia_pair,
    validate_competencia_limit,
)
from app.shared.pagination import PagedResponse, PageParams
from app.shared.utils.data_normalization import (
    normalize_digits,
    normalize_plate,
    normalize_upper_text,
    parse_decimal_br,
)
from app.shared.utils.cpf_cnpj import (
    format_cnpj,
    format_cpf,
    validate_cnpj,
    validate_cpf,
    validate_cpf_or_cnpj,
)


class TestCPFValidation:
    def test_valid_cpf(self) -> None:
        assert validate_cpf("52998224725") is True

    def test_invalid_cpf_all_same(self) -> None:
        assert validate_cpf("11111111111") is False

    def test_invalid_cpf_wrong_digit(self) -> None:
        assert validate_cpf("12345678901") is False

    def test_invalid_cpf_wrong_length(self) -> None:
        assert validate_cpf("123") is False

    def test_format_cpf(self) -> None:
        assert format_cpf("52998224725") == "529.982.247-25"


class TestCNPJValidation:
    def test_valid_cnpj(self) -> None:
        assert validate_cnpj("11222333000181") is True

    def test_invalid_cnpj_all_same(self) -> None:
        assert validate_cnpj("11111111111111") is False

    def test_invalid_cnpj_wrong_length(self) -> None:
        assert validate_cnpj("123") is False

    def test_format_cnpj(self) -> None:
        result = format_cnpj("11222333000181")
        assert "/" in result and "-" in result


class TestValidateCPFOrCNPJ:
    def test_valid_cpf(self) -> None:
        assert validate_cpf_or_cnpj("52998224725") is True

    def test_valid_cnpj(self) -> None:
        assert validate_cpf_or_cnpj("11222333000181") is True

    def test_invalid_length(self) -> None:
        assert validate_cpf_or_cnpj("123") is False


class TestDataNormalization:
    def test_normalize_upper_text(self) -> None:
        assert normalize_upper_text("  joão silva  ") == "JOÃO SILVA"

    def test_normalize_plate(self) -> None:
        assert normalize_plate("abc-1d23") == "ABC1D23"

    def test_normalize_digits(self) -> None:
        assert normalize_digits("529.982.247-25") == "52998224725"

    def test_parse_decimal_br_comma(self) -> None:
        assert parse_decimal_br("30.000,50") == 30000.5

    def test_parse_decimal_br_dot(self) -> None:
        assert parse_decimal_br("5500.00") == 5500.0


class TestPagination:
    def test_page_params_offset(self) -> None:
        params = PageParams(page=3, size=10)
        assert params.offset == 20
        assert params.limit == 10

    def test_page_params_first_page(self) -> None:
        params = PageParams(page=1, size=20)
        assert params.offset == 0

    def test_paged_response_create(self) -> None:
        items = [1, 2, 3, 4, 5]
        params = PageParams(page=1, size=5)
        result = PagedResponse.create(items, total=50, params=params)
        assert result.total == 50
        assert result.pages == 10
        assert result.has_next is True
        assert result.has_prev is False

    def test_paged_response_last_page(self) -> None:
        items = [1, 2]
        params = PageParams(page=5, size=5)
        result = PagedResponse.create(items, total=22, params=params)
        assert result.has_prev is True
        assert result.has_next is False

    def test_paged_response_empty(self) -> None:
        params = PageParams(page=1, size=20)
        result = PagedResponse.create([], total=0, params=params)
        assert result.total == 0
        assert result.pages == 1
        assert result.has_next is False
        assert result.has_prev is False


class TestCompetenciaLimit:
    def test_current_month_ok(self) -> None:
        today = date(2026, 9, 5)
        assert is_competencia_within_limit(2026, 9, today=today) is True

    def test_two_months_ahead_ok(self) -> None:
        today = date(2026, 9, 5)
        assert is_competencia_within_limit(2026, 11, today=today) is True

    def test_three_months_ahead_false(self) -> None:
        today = date(2026, 9, 5)
        assert is_competencia_within_limit(2026, 12, today=today) is False

    def test_past_month_true(self) -> None:
        today = date(2026, 9, 5)
        assert is_competencia_within_limit(2026, 1, today=today) is True
        assert is_competencia_within_limit(2025, 12, today=today) is True

    def test_year_boundary(self) -> None:
        today = date(2026, 11, 30)
        assert is_competencia_within_limit(2027, 1, today=today) is True
        assert is_competencia_within_limit(2027, 2, today=today) is False

    def test_validate_raises(self) -> None:
        today = date(2026, 9, 5)
        with pytest.raises(BadRequestException, match="2 meses à frente"):
            validate_competencia_limit(2026, 12, today=today)

    def test_resolve_pair_both_none(self) -> None:
        assert resolve_competencia_pair(None, None) == (None, None)

    def test_resolve_pair_partial_raises(self) -> None:
        with pytest.raises(BadRequestException, match="juntos"):
            resolve_competencia_pair(9, None)
        with pytest.raises(BadRequestException, match="juntos"):
            resolve_competencia_pair(None, 2026)
