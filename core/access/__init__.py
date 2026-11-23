"""
core/access
───────────
Sistema de control de acceso por suscripción.

Provee validación de features habilitadas y enforcement de topes
de uso (diarios, por suscripción, por ventana de tiempo) usando Redis
como almacén de contadores de alta velocidad.

Imports rápidos
───────────────
    from core.access import AccessChecker, AccessResult
    from core.access import HasSubscriptionAccess, track_usage
    from core.access import warmup_subscription_cache
"""

from .checker import AccessChecker
from .enforcement import enforcement_registry, USERS_QUOTA_FEATURE
from .result import AccessResult
from .decorators import track_usage, untrack_usage
from .registry import usage_registry
from .reconcile import reconcile_company_quotas
from .warmup import warmup_subscription_cache

__all__ = [
    'AccessChecker',
    'AccessResult',
    'track_usage',
    'untrack_usage',
    'usage_registry',
    'enforcement_registry',
    'USERS_QUOTA_FEATURE',
    'reconcile_company_quotas',
    'warmup_subscription_cache',
]
