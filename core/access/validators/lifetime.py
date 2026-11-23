"""
core/access/validators/lifetime.py
──────────────────────────────────
Validador de topes lifetime (por suscripción).

Dos modos según registro en enforcement_registry:
  • Cupo de activos → COUNT en BD vía adaptador.
  • Eventos acumulados → contador Redis (track/untrack).
"""

from __future__ import annotations

import logging

from .base import LimitValidator
from core.access.enforcement import enforcement_registry
from core.access.store import UsageStore

logger = logging.getLogger('app.api')

_FAIL_CLOSED_USAGE = 2**31 - 1


class LifetimeValidator(LimitValidator):
    """Valida que el consumo no exceda el tope del plan (lifetime)."""

    def matches(self, validation_type: str) -> bool:
        return validation_type == 'lifetime'

    def get_current_usage(self, company_id: str, feature_key: str, **kwargs) -> int:
        if enforcement_registry.has(feature_key):
            count = enforcement_registry.count_active(feature_key, company_id)
            if count is None:
                logger.error(
                    'lifetime quota count failed — denying feature=%s company=%s',
                    feature_key, company_id,
                )
                return _FAIL_CLOSED_USAGE
            return count
        return UsageStore.get_lifetime(company_id, feature_key)

    def track(self, company_id: str, feature_key: str, **kwargs) -> int:
        if enforcement_registry.has(feature_key):
            count = enforcement_registry.count_active(feature_key, company_id)
            return count if count is not None else 0
        return UsageStore.increment_lifetime(company_id, feature_key)

    def untrack(self, company_id: str, feature_key: str, **kwargs) -> int:
        if enforcement_registry.has(feature_key):
            count = enforcement_registry.count_active(feature_key, company_id)
            return count if count is not None else 0
        return UsageStore.decrement_lifetime(company_id, feature_key)
