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


class ImplementType(StrEnum):
    CARRETA = "carreta"
    BAU = "bau"
    TANQUE = "tanque"
    PRANCHA = "prancha"
    CAMERA_FRIA = "camera_fria"


class DriverDocumentType(StrEnum):
    PHOTO = "photo"
    CNH_FRONT = "cnh_front"
    CNH_BACK = "cnh_back"
    OTHER = "other"


class DriverStatus(StrEnum):
    ATIVO = "ativo"
    INATIVO = "inativo"
    SUSPENSO = "suspenso"
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


class NotificationType(StrEnum):
    TRACKING_OCCURRENCE = "tracking_occurrence"
    FUEL_REFILL = "fuel_refill"
    TOLL_CHARGE = "toll_charge"


# Frete em viagem — motorista pode registrar abastecimento/ocorrências
ACTIVE_FREIGHT_STATUSES: frozenset[FreightStatus] = frozenset({
    FreightStatus.CONFIRMADO,
    FreightStatus.EM_COLETA,
    FreightStatus.EM_TRANSPORTE,
})


TRACKING_STATUS_LABELS: dict[str, str] = {
    TrackingStatus.COLETADO: "Coletado",
    TrackingStatus.EM_TRANSITO: "Em trânsito",
    TrackingStatus.SAIU_PARA_ENTREGA: "Saiu para entrega",
    TrackingStatus.TENTATIVA_ENTREGA: "Tentativa de entrega",
    TrackingStatus.ENTREGUE: "Entregue",
    TrackingStatus.DEVOLVIDO: "Devolvido",
}


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
