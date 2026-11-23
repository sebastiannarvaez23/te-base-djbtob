"""
core/access/validators/window.py
────────────────────────────────
Validador de topes por ventana de tiempo fija.

La ventana dura ``window_hours`` horas y está alineada al reloj (epoch UTC).
Sin ``window_hours`` válido el validador falla cerrado (no asume 1 h).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from core.access.store import UsageStore
from core.access.window_hours import coerce_window_hours

from .base import LimitValidator

logger = logging.getLogger('app.api')


class WindowValidator(LimitValidator):
    """Valida que el consumo de la ventana actual no exceda el tope."""

    def matches(self, validation_type: str) -> bool:
        return validation_type == 'window'

    @staticmethod
    def resolve_hours(kwargs: dict) -> Optional[int]:
        try:
            return coerce_window_hours(kwargs.get('window_hours'))
        except ValueError:
            return None

    def get_current_usage(self, company_id: str, feature_key: str, **kwargs) -> int:
        hours = self.resolve_hours(kwargs)
        if hours is None:
            logger.error(
                'window limit misconfigured company=%s feature=%s (missing/invalid window_hours)',
                company_id, feature_key,
            )
            # Fail-closed: treat as exhausted so check_feature denies.
            return 2**31 - 1
        return UsageStore.get_window(company_id, feature_key, hours)

    def track(self, company_id: str, feature_key: str, **kwargs) -> int:
        hours = self.resolve_hours(kwargs)
        if hours is None:
            logger.error(
                'window track skipped company=%s feature=%s (missing/invalid window_hours)',
                company_id, feature_key,
            )
            return 0
        return UsageStore.increment_window(company_id, feature_key, hours)

    def quota_resets_at(self, **kwargs) -> Optional[datetime]:
        hours = self.resolve_hours(kwargs)
        if hours is None:
            return None
        return UsageStore.window_reset_at(hours)
