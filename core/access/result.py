"""
core/access/result.py
─────────────────────
Value object que encapsula el resultado de una verificación de acceso.
"""

from __future__ import annotations

from datetime import datetime, timezone

from core.errors.codes import AppErrorCode


class AccessResult:
    """Resultado inmutable de una verificación de acceso por suscripción."""

    __slots__ = ('is_allowed', 'error_code', 'detail', 'context')

    def __init__(
        self,
        is_allowed: bool,
        error_code: AppErrorCode | None = None,
        detail: str = '',
        context: dict | None = None,
    ):
        self.is_allowed = is_allowed
        self.error_code = error_code
        self.detail = detail
        self.context = context or {}

    # ── Constructores semánticos ──────────────────────────────────────

    @classmethod
    def allowed(cls) -> AccessResult:
        return cls(is_allowed=True)

    @classmethod
    def no_subscription(cls) -> AccessResult:
        return cls(
            is_allowed=False,
            error_code=AppErrorCode.SUB_NO_ACTIVE,
            detail='This company does not have an active subscription plan.',
        )

    @classmethod
    def feature_denied(cls, feature_key: str) -> AccessResult:
        return cls(
            is_allowed=False,
            error_code=AppErrorCode.SUB_FEATURE_DENIED,
            detail=f'The feature "{feature_key}" is not included in the current plan.',
            context={'feature_key': feature_key},
        )

    @classmethod
    def module_inactive(cls, *, module_code: str = '', feature_key: str = '') -> AccessResult:
        ctx = {}
        if module_code:
            ctx['module_code'] = module_code
        if feature_key:
            ctx['feature_key'] = feature_key
        return cls(
            is_allowed=False,
            error_code=AppErrorCode.MODULE_INACTIVE,
            detail='This module has been deactivated.',
            context=ctx,
        )

    @classmethod
    def section_inactive(cls, *, section_code: str = '', module_code: str = '') -> AccessResult:
        ctx = {}
        if section_code:
            ctx['section_code'] = section_code
        if module_code:
            ctx['module_code'] = module_code
        return cls(
            is_allowed=False,
            error_code=AppErrorCode.SECTION_INACTIVE,
            detail='This section has been deactivated.',
            context=ctx,
        )

    @classmethod
    def functionality_inactive(cls, feature_key: str) -> AccessResult:
        return cls(
            is_allowed=False,
            error_code=AppErrorCode.FUNC_INACTIVE,
            detail=f'The functionality "{feature_key}" has been deactivated.',
            context={'feature_key': feature_key},
        )

    @classmethod
    def quota_exceeded(
        cls,
        feature_key: str,
        max_value: int,
        current: int,
        validation_type: str,
        *,
        resets_at: datetime | None = None,
    ) -> AccessResult:
        context: dict = {
            'feature_key': feature_key,
            'max_value': max_value,
            'current_usage': current,
            'validation_type': validation_type,
        }
        if resets_at is not None:
            if resets_at.tzinfo is None:
                resets_at = resets_at.replace(tzinfo=timezone.utc)
            context['resets_at'] = resets_at.isoformat()
        return cls(
            is_allowed=False,
            error_code=AppErrorCode.SUB_QUOTA_EXCEEDED,
            detail=(
                f'Usage limit reached for "{feature_key}": '
                f'{current}/{max_value} ({validation_type}).'
            ),
            context=context,
        )
