"""
core/access/registry.py
───────────────────────
Registro de contadores reales (consultas a BD) para validación
de topes por suscripción (lifetime).

Cada feature key que requiera validación lifetime debe registrar
una función que, dado un company_id, retorne el conteo actual de
registros en la tabla correspondiente.

Uso
───
    from core.access.registry import usage_registry

    # En el apps.py del módulo (ready()):
    usage_registry.register(
        'settings.payment-methods.create',
        lambda company_id: PaymentMethod.objects.filter(company_id=company_id).count(),
    )

    # El LifetimeValidator usará esta función automáticamente.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

logger = logging.getLogger('app.api')


class UsageCounterRegistry:
    """Registro global de funciones que cuentan registros reales en BD."""

    def __init__(self):
        self._counters: dict[str, Callable[[str], int]] = {}

    def register(self, feature_key: str, counter_fn: Callable[[str], int]) -> None:
        """Registra una función que cuenta el uso real para una feature key.

        Args:
            feature_key: clave de la funcionalidad (ej: 'settings.payment-methods.create').
            counter_fn:  callable que recibe company_id (str) y retorna int (conteo real).
        """
        self._counters[feature_key] = counter_fn

    def get_count(self, feature_key: str, company_id: str) -> Optional[int]:
        """Retorna el conteo real de la BD, o None si no hay counter registrado.

        Args:
            feature_key: clave de la funcionalidad.
            company_id:  UUID de la empresa como string.

        Returns:
            int con el conteo real, o None si la feature key no tiene counter.
        """
        counter_fn = self._counters.get(feature_key)
        if counter_fn is None:
            return None
        try:
            return counter_fn(company_id)
        except Exception:
            logger.warning(
                'Error al contar uso real para feature=%s company=%s',
                feature_key, company_id,
                exc_info=True,
            )
            return None

    def has_counter(self, feature_key: str) -> bool:
        return feature_key in self._counters

    @property
    def registered_keys(self) -> list[str]:
        return list(self._counters.keys())


# Instancia global (singleton)
usage_registry = UsageCounterRegistry()
