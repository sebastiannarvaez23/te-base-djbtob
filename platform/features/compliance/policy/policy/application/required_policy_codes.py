"""Adapter: códigos required-on-login desde settings (capa application)."""

from __future__ import annotations

from typing import Tuple

from platform.features.compliance.policy.policy.domain.required_codes import (
    DEFAULT_CLIENT_LOGIN_REQUIRED_POLICY_CODES,
    ONBOARDING_PRIVACY_POLICY_CODE,
    ONBOARDING_TERMS_POLICY_CODE,
    normalize_policy_codes,
)


def get_client_login_required_policy_codes() -> Tuple[str, ...]:
    """Códigos que bloquean acceso operativo hasta firmarse.

    - Settings ``CLIENT_LOGIN_REQUIRED_POLICY_CODES`` si está definido.
    - Si no, ``DEFAULT_CLIENT_LOGIN_REQUIRED_POLICY_CODES``.
    - Tupla vacía ⇒ no hay gate de políticas en login (nada pendiente).
    """
    try:
        from django.conf import settings

        if hasattr(settings, 'CLIENT_LOGIN_REQUIRED_POLICY_CODES'):
            return normalize_policy_codes(settings.CLIENT_LOGIN_REQUIRED_POLICY_CODES)
    except Exception:
        pass
    return normalize_policy_codes(DEFAULT_CLIENT_LOGIN_REQUIRED_POLICY_CODES)


def get_client_onboarding_required_policy_codes() -> Tuple[str, ...]:
    """Códigos que el finalize debe sellar (privacy + terms).

    El gate de login puede exigir códigos adicionales vía settings; esos se
    firman post-login. El body de finalize solo aporta hashes de privacy y
    términos.
    """
    return (
        ONBOARDING_PRIVACY_POLICY_CODE,
        ONBOARDING_TERMS_POLICY_CODE,
    )
