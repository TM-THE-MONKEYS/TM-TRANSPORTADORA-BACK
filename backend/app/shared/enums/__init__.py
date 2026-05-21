"""Shared enums used across the application."""
from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    OPERADOR = "operador"
    FINANCEIRO = "financeiro"
    MOTORISTA = "motorista"


class TruckStatus(StrEnum):
    DISPONIVEL = "disponivel"
    EM_VIAGEM = "em_viagem"
    EM_MANUTENCAO = "em_manutencao"
    INATIVO = "inativo"


class DriverStatus(StrEnum):
    ATIVO = "ativo"
    INATIVO = "inativo"
    SUSPENS0 = "suspenso"
    FERIAS = "ferias"


class FreightStatus(StrEnum):
    ORCAMENTO = "orcamento"
    CONFIRMADO = "confirmado"
    EM_COLETA = "em_coleta"
    EM_TRANSPORTE = "em_transporte"
    ENTREGUE = "entregue"
    CANCELADO = "cancelado"


class MaintenanceType(StrEnum):
    PREVENTIVA = "preventiva"
    CORRETIVA = "corretiva"


class MaintenanceStatus(StrEnum):
    AGENDADA = "agendada"
    EM_ANDAMENTO = "em_andamento"
    CONCLUIDA = "concluida"
    CANCELADA = "cancelada"


class FinanceEntryType(StrEnum):
    RECEITA = "receita"
    DESPESA = "despesa"


class FinanceEntryStatus(StrEnum):
    PENDENTE = "pendente"
    PAGO = "pago"
    CANCELADO = "cancelado"
    VENCIDO = "vencido"


class TrackingStatus(StrEnum):
    COLETADO = "coletado"
    EM_TRANSITO = "em_transito"
    SAIU_PARA_ENTREGA = "saiu_para_entrega"
    TENTATIVA_ENTREGA = "tentativa_entrega"
    ENTREGUE = "entregue"
    DEVOLVIDO = "devolvido"


class CNHCategory(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    AB = "AB"
    AC = "AC"
    AD = "AD"
    AE = "AE"
