"""Query-param helpers for competência mês/ano."""
from __future__ import annotations

from typing import Annotated, NamedTuple

from fastapi import Depends, Query

from app.shared.filters.competencia import (
    resolve_competencia_pair,
    validate_competencia_limit,
)


class OptionalCompetencia(NamedTuple):
    mes: int | None
    ano: int | None


class RequiredCompetencia(NamedTuple):
    mes: int
    ano: int


def get_optional_competencia(
    competencia_mes: int | None = Query(default=None, ge=1, le=12),
    competencia_ano: int | None = Query(default=None, ge=2000, le=2100),
) -> OptionalCompetencia:
    mes, ano = resolve_competencia_pair(competencia_mes, competencia_ano)
    return OptionalCompetencia(mes=mes, ano=ano)


def get_required_competencia(
    competencia_mes: int = Query(ge=1, le=12),
    competencia_ano: int = Query(ge=2000, le=2100),
) -> RequiredCompetencia:
    validate_competencia_limit(competencia_ano, competencia_mes)
    return RequiredCompetencia(mes=competencia_mes, ano=competencia_ano)


OptionalCompetenciaDep = Annotated[
    OptionalCompetencia, Depends(get_optional_competencia)
]
RequiredCompetenciaDep = Annotated[
    RequiredCompetencia, Depends(get_required_competencia)
]
