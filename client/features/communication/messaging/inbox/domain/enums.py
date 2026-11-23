from enum import Enum


class NotificationKind(str, Enum):
    SHARE = 'SHARE'
    ADMIN_DIRECT = 'ADMIN_DIRECT'
    ADMIN_COMPANY = 'ADMIN_COMPANY'
    ADMIN_BROADCAST = 'ADMIN_BROADCAST'


class ActorKind(str, Enum):
    USER = 'USER'
    ADMIN = 'ADMIN'
    SYSTEM = 'SYSTEM'


class ReadStatus(str, Enum):
    """Filtro de listado de la campanita."""
    ALL = 'all'
    UNREAD = 'unread'
    READ = 'read'
