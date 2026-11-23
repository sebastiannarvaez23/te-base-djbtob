"""Códigos de error — system."""
from enum import Enum


class ValidationErrorCode(str, Enum):
    """Validación."""

    VALIDATION_ERROR = 'VAL_001'  # Uno o más campos inválidos


VAL_REGISTRY: dict[ValidationErrorCode, dict] = {
    ValidationErrorCode.VALIDATION_ERROR: {
        'http_status': 400,
        'message': 'Validation error',
        'detail': 'One or more fields contain invalid values.',
    },
}


class ServerErrorCode(str, Enum):
    """Servidor."""

    SERVER_ERROR          = 'SRV_001'  # Error interno inesperado
    SERVER_DATABASE_ERROR = 'SRV_002'  # Error al procesar en base de datos


SRV_REGISTRY: dict[ServerErrorCode, dict] = {
    ServerErrorCode.SERVER_ERROR: {
        'http_status': 500,
        'message': 'Internal server error',
        'detail': 'An unexpected error occurred. Please try again later.',
    },
    ServerErrorCode.SERVER_DATABASE_ERROR: {
        'http_status': 500,
        'message': 'Database error',
        'detail': 'An error occurred while processing the database request.',
    },
}


class RateLimitErrorCode(str, Enum):
    """Límite de tasa HTTP (capa transversal)."""

    RATE_LIMITED = 'RL_001'  # Throttle de plataforma (DRF u otro corte transversal)


RL_REGISTRY: dict[RateLimitErrorCode, dict] = {
    RateLimitErrorCode.RATE_LIMITED: {
        'http_status': 429,
        'message': 'Too many requests',
        'detail': 'Too many requests.',
    },
}


class HttpErrorCode(str, Enum):
    """Errores HTTP del framework (Django/DRF) sin código de dominio."""

    HTTP_NOT_FOUND = 'HTTP_001'  # Django Http404


HTTP_REGISTRY: dict[HttpErrorCode, dict] = {
    HttpErrorCode.HTTP_NOT_FOUND: {
        'http_status': 404,
        'message': 'Resource not found',
        'detail': 'The requested resource does not exist or was deleted.',
    },
}

__all__ = [
    'ValidationErrorCode',
    'ServerErrorCode',
    'RateLimitErrorCode',
    'HttpErrorCode',
    'VAL_REGISTRY',
    'SRV_REGISTRY',
    'RL_REGISTRY',
    'HTTP_REGISTRY',
]
