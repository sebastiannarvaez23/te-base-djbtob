"""
Modo de acceso restringido para administradores de empresa con suscripción
no activa por falta de pago (p. ej. ``suspended`` tras fallo de renovación).

Permite login y uso exclusivo de configuración → suscripción y medios de pago.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from core.access.enforcement import ADMIN_ROLE_NAME

AccessMode = Literal['full', 'billing_recovery']

# Features permitidas sin plan activo (allowlist explícita).
BILLING_RECOVERY_FEATURES: frozenset[str] = frozenset({
    'settings.subscription.view',
    'settings.subscription.upgrade',
    'settings.subscription.apply-voucher',
    'settings.subscription.view-voucher-applied',
    'settings.payment-methods.view',
    'settings.payment-methods.create',
    'settings.payment-methods.edit',
    'settings.payment-methods.toggle',
    'settings.payment-methods.delete',
})

# Único módulo de sidebar visible en recovery.
BILLING_RECOVERY_MODULE_CODE = 'settings'

# Rutas API permitidas con JWT en modo recovery (prefijos tras ``/api/v1/``).
# Mantener alineado con ``BILLING_RECOVERY_FEATURES`` (mismos dominios de
# configuración / facturación; aquí son paths HTTP, allí feature keys).
BILLING_RECOVERY_API_PREFIXES: tuple[str, ...] = (
    'billing/subscriptions',
    'billing/payment-methods',
    'promotions/',
    'auth/me',
    'auth/refresh',
    'auth/logout',
)

# Estados de adquisición que habilitan recovery para el admin de empresa.
RECOVERABLE_SUBSCRIPTION_STATUSES: frozenset[str] = frozenset({'suspended'})


@dataclass(frozen=True)
class LoginAccessResult:
    mode: AccessMode
    subscription_status: Optional[str] = None

    @property
    def is_billing_recovery(self) -> bool:
        return self.mode == 'billing_recovery'


def is_company_admin(user) -> bool:
    rol = getattr(user, 'rol', None)
    return bool(rol and getattr(rol, 'name', None) == ADMIN_ROLE_NAME)


def resolve_login_access(user, latest_acquisition) -> LoginAccessResult:
    """Determina el modo de acceso tras validar credenciales.

    Args:
        user: instancia ORM del usuario tenant.
        latest_acquisition: última ``CompanySubscription`` de la empresa
            (``order_by('-start_date').first()``), o ``None``.
    """
    from platform.features.billing.subscription.subscription.models import CompanySubscription

    if latest_acquisition is None:
        if is_company_admin(user):
            return LoginAccessResult(mode='billing_recovery', subscription_status=None)
        return LoginAccessResult(mode='full', subscription_status=None)

    status = latest_acquisition.status
    if status == CompanySubscription.Status.ACTIVE:
        return LoginAccessResult(mode='full', subscription_status=status)

    if status in RECOVERABLE_SUBSCRIPTION_STATUSES and is_company_admin(user):
        return LoginAccessResult(mode='billing_recovery', subscription_status=status)

    return LoginAccessResult(mode='full', subscription_status=status)


def is_billing_recovery_feature(feature_key: str) -> bool:
    return feature_key in BILLING_RECOVERY_FEATURES


def fetch_latest_acquisition(company):
    """Última adquisición de la empresa (cualquier estado)."""
    from platform.features.billing.subscription.subscription.models import CompanySubscription

    if company is None:
        return None
    return (
        CompanySubscription.objects
        .filter(company=company)
        .select_related('subscription')
        .order_by('-start_date')
        .first()
    )


def resolve_login_access_for_user(user) -> LoginAccessResult:
    """Modo de acceso para un usuario ya autenticado (sesión / refresh JWT)."""
    company = getattr(user, 'company', None)
    if company is None:
        return LoginAccessResult(mode='full', subscription_status=None)
    return resolve_login_access(user, fetch_latest_acquisition(company))


def resolve_access_mode_for_user(user) -> AccessMode:
    """Atajo para refresh JWT: solo el modo, sin estado de suscripción."""
    return resolve_login_access_for_user(user).mode


def get_request_access_mode(request) -> AccessMode:
    """Lee ``access_mode`` del JWT (DRF ``request.auth``) o del middleware."""
    auth = getattr(request, 'auth', None)
    if isinstance(auth, dict):
        mode = auth.get('access_mode')
        if mode:
            return mode
    middleware_mode = getattr(request, 'access_mode', None)
    if middleware_mode:
        return middleware_mode
    return 'full'


def _api_v1_relative_path(path: str) -> str:
    marker = '/api/v1/'
    idx = path.find(marker)
    if idx >= 0:
        return path[idx + len(marker):]
    return path.lstrip('/')


def is_billing_recovery_api_path(path: str) -> bool:
    """True si la ruta HTTP está en la allowlist de recovery."""
    relative = _api_v1_relative_path(path)
    for prefix in BILLING_RECOVERY_API_PREFIXES:
        if relative == prefix.rstrip('/') or relative.startswith(prefix):
            return True
    return False
