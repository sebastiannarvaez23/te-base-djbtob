"""Strangler shim — implementation lives in ``necore.errors.exceptions``."""

from necore.errors.exceptions import (  # noqa: F401
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

__all__ = [
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
