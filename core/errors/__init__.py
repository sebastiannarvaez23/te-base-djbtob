"""
core/errors
───────────
Sistema centralizado de manejo de errores de la aplicación.

Imports rápidos
───────────────
    from core.errors import AppErrorCode
    from core.errors import (
        AppException, AuthException, PermissionException,
        NotFoundException, ConflictException, ValidationAppException,
        RateLimitException, ServerException,
    )
"""

from necore.errors.registry import configure_error_registry

from .codes import AppErrorCode, ERROR_REGISTRY
from .exceptions import (
    AppException,
    AuthException,
    ConflictException,
    EmailNotVerifiedException,
    NotFoundException,
    OnboardingException,
    PermissionException,
    RateLimitException,
    ServerException,
    SubscriptionException,
    ValidationAppException,
)

# Ensure portable necore modules can resolve product codes even before AppConfig.ready().
configure_error_registry(AppErrorCode, ERROR_REGISTRY)

__all__ = [
    # Códigos
    'AppErrorCode',
    'ERROR_REGISTRY',
    # Excepciones
    'AppException',
    'AuthException',
    'EmailNotVerifiedException',
    'PermissionException',
    'SubscriptionException',
    'NotFoundException',
    'ConflictException',
    'ValidationAppException',
    'ServerException',
    'OnboardingException',
    'RateLimitException',
]
