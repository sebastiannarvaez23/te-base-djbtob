"""
core/access/validators/base.py
──────────────────────────────
Contrato abstracto para validadores de topes de uso.

Cada tipo de validación (diaria, por suscripción, etc.) implementa
esta interfaz. El AccessChecker selecciona el validador correcto
según el validation_type del tope configurado.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional


class LimitValidator(ABC):
    """Interfaz base para validadores de límites de suscripción."""

    @abstractmethod
    def matches(self, validation_type: str) -> bool:
        """Retorna True si este validador maneja el tipo de validación dado."""
        ...

    @abstractmethod
    def get_current_usage(self, company_id: str, feature_key: str, **kwargs) -> int:
        """Retorna el consumo actual según la lógica de este tipo de validación."""
        ...

    @abstractmethod
    def track(self, company_id: str, feature_key: str, **kwargs) -> int:
        """Incrementa el contador de uso y retorna el nuevo valor."""
        ...

    def untrack(self, company_id: str, feature_key: str, **kwargs) -> int:
        """Decrementa el contador de uso (al eliminar un recurso).

        Implementación por defecto: no-op (retorna 0).
        Solo los validadores que lo necesiten lo sobreescriben (ej: lifetime).
        """
        return 0

    def quota_resets_at(self, **kwargs) -> Optional[datetime]:
        """Instante UTC en el que se recarga el cupo, o None si no aplica."""
        return None

    def validate(self, company_id: str, feature_key: str, max_value: int, **kwargs) -> bool:
        """Retorna True si el consumo actual es menor al tope.

        Implementación por defecto: compara get_current_usage contra max_value.
        Se puede sobreescribir para lógica especial.
        """
        return self.get_current_usage(company_id, feature_key, **kwargs) < max_value
