"""
core/access/enforcement.py
──────────────────────────
Registro de adaptadores para topes de entidades *activas*.

Guía para implementar más dominios:
  platform/features/billing/quota_enforcement/EXTENDING.md

Resumen
───────
  • Tope en admin: SubscriptionLimit (lifetime) + feature_key.
  • Adaptador: count_active, list_active_entity_ids (orden conservar→sacar),
    protected_entity_ids, deactivate (sin delete).
  • Registrar en AppConfig.ready() del módulo del dominio.
  • Use case: ensure_quota_or_raise al crear y al activar.
  • Reconciliación automática: PeriodIssued (no tocar billing).

Referencia: client/features/security/registration/quota_adapters.py
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from typing import Callable, Optional

logger = logging.getLogger('app.api')

ADMIN_ROLE_NAME = 'Administrator'
USERS_QUOTA_FEATURE = 'security.users.create'


class IQuotaEntityAdapter(ABC):
    """
    Puerto para un tope ``lifetime`` basado en cantidad de activos.

    Ver EXTENDING.md para checklist completo al implementar bodegas,
    referencias u otros dominios.
    """

    @property
    @abstractmethod
    def feature_key(self) -> str:
        ...

    @abstractmethod
    def count_active(self, company_id: str) -> int:
        ...

    @abstractmethod
    def list_active_entity_ids(self, company_id: str) -> list[uuid.UUID]:
        """
        IDs activos en orden de conservación.

        Los primeros se mantienen al reconciliar; los últimos se inactivan
        primero (reversed en reconcile.py). Orden típico: más antiguo primero
        (``order_by('id')`` o ``created_at``).
        """

    @abstractmethod
    def protected_entity_ids(self, company_id: str) -> set[uuid.UUID]:
        """Nunca se inactivan en reconciliación (ej. admin)."""

    @abstractmethod
    def deactivate(self, entity_id: uuid.UUID, company_id: str) -> None:
        ...


class EnforcementRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, IQuotaEntityAdapter] = {}

    def register(self, adapter: IQuotaEntityAdapter) -> None:
        key = adapter.feature_key
        self._adapters[key] = adapter

    def register_factory(
        self,
        feature_key: str,
        factory: Callable[[], IQuotaEntityAdapter],
    ) -> None:
        """Registra un adaptador construido bajo demanda (evita import cycles)."""
        self._adapters[feature_key] = _LazyAdapter(factory)

    def has(self, feature_key: str) -> bool:
        return feature_key in self._adapters

    def get(self, feature_key: str) -> Optional[IQuotaEntityAdapter]:
        return self._adapters.get(feature_key)

    def count_active(self, feature_key: str, company_id: str) -> Optional[int]:
        adapter = self.get(feature_key)
        if adapter is None:
            return None
        try:
            return adapter.count_active(company_id)
        except Exception:
            logger.warning(
                'quota count_active failed feature=%s company=%s',
                feature_key, company_id, exc_info=True,
            )
            return None

    @property
    def registered_keys(self) -> list[str]:
        return list(self._adapters.keys())


class _LazyAdapter(IQuotaEntityAdapter):
    def __init__(self, factory: Callable[[], IQuotaEntityAdapter]) -> None:
        self._factory = factory
        self._resolved: Optional[IQuotaEntityAdapter] = None

    def _a(self) -> IQuotaEntityAdapter:
        if self._resolved is None:
            self._resolved = self._factory()
        return self._resolved

    @property
    def feature_key(self) -> str:
        return self._a().feature_key

    def count_active(self, company_id: str) -> int:
        return self._a().count_active(company_id)

    def list_active_entity_ids(self, company_id: str) -> list[uuid.UUID]:
        return self._a().list_active_entity_ids(company_id)

    def protected_entity_ids(self, company_id: str) -> set[uuid.UUID]:
        return self._a().protected_entity_ids(company_id)

    def deactivate(self, entity_id: uuid.UUID, company_id: str) -> None:
        self._a().deactivate(entity_id, company_id)


enforcement_registry = EnforcementRegistry()
