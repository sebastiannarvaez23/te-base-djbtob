"""
core/access/validators/daily.py
───────────────────────────────
Validador de topes diarios.

Cada día se reinicia el contador automáticamente gracias al TTL
de 48h en Redis (la clave incluye la fecha).
"""

from datetime import datetime
from typing import Optional

from .base import LimitValidator
from core.access.store import UsageStore


class DailyValidator(LimitValidator):
    """Valida que el consumo del día actual no exceda el tope."""

    def matches(self, validation_type: str) -> bool:
        return validation_type == 'daily'

    def get_current_usage(self, company_id: str, feature_key: str, **kwargs) -> int:
        return UsageStore.get_daily(company_id, feature_key)

    def track(self, company_id: str, feature_key: str, **kwargs) -> int:
        return UsageStore.increment_daily(company_id, feature_key)

    def quota_resets_at(self, **kwargs) -> Optional[datetime]:
        return UsageStore.daily_reset_at()
