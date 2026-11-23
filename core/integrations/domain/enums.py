"""Enumeraciones del dominio de integraciones."""

from enum import Enum


class ConnectorKind(str, Enum):
    ERP = 'ERP'
    PROVIDER = 'PROVIDER'
    APP = 'APP'


class ConnectorProvider(str, Enum):
    FAKE = 'fake'
    SAP = 'sap'
    SIESA = 'siesa'
    WEBHOOK_INBOUND = 'webhook_inbound'


class SyncDirection(str, Enum):
    INBOUND = 'INBOUND'
    OUTBOUND = 'OUTBOUND'


class Environment(str, Enum):
    PROSANDBOX = 'PROSANDBOX'
    CLIENT_TEST = 'CLIENT_TEST'
    CLIENT_PROD = 'CLIENT_PROD'


class SyncStatus(str, Enum):
    SUCCESS = 'SUCCESS'
    PARTIAL = 'PARTIAL'
    FAILED = 'FAILED'


class CircuitState(str, Enum):
    CLOSED = 'CLOSED'
    OPEN = 'OPEN'
    HALF_OPEN = 'HALF_OPEN'
