"""Enumeraciones compartidas del dominio de notificaciones.

Viven en el lado público porque tanto el outbox del admin (público) como
el inbox del tenant (cliente) las consumen, y la dirección de dependencia
permitida es client → platform.
"""

from enum import Enum


class AudienceScope(str, Enum):
    """Alcance de un envío del administrador."""
    SINGLE_USER = 'SINGLE_USER'
    COMPANY_USERS = 'COMPANY_USERS'
    ALL_TENANTS = 'ALL_TENANTS'


class OutboxStatus(str, Enum):
    PENDING = 'PENDING'
    DISPATCHING = 'DISPATCHING'
    SENT = 'SENT'
    FAILED = 'FAILED'


class NotificationLevel(str, Enum):
    INFO = 'INFO'
    SUCCESS = 'SUCCESS'
    WARNING = 'WARNING'


class ReadStatus(str, Enum):
    """Filtro de listado de la campanita (admin o tenant)."""
    ALL = 'all'
    UNREAD = 'unread'
    READ = 'read'
