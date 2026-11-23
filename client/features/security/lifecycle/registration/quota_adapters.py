"""
Adaptadores de cupo activo — schema público.

REFERENCIA para nuevos dominios. Copiar este patrón en el módulo del
recurso (warehouse, reference, …) y registrar en su AppConfig.ready().

Guía: platform/features/billing/quota_enforcement/EXTENDING.md

Pendiente (topes por definir en producto):
  • Bodegas — feature_key y criterio ACTIVE a confirmar
  • Referencias — inventories.references-create (u otra key)
"""

from __future__ import annotations

import uuid

from core.access.enforcement import (
    ADMIN_ROLE_NAME,
    IQuotaEntityAdapter,
    USERS_QUOTA_FEATURE,
    enforcement_registry,
)


class CompanyUsersQuotaAdapter(IQuotaEntityAdapter):
    feature_key = USERS_QUOTA_FEATURE

    def count_active(self, company_id: str) -> int:
        from client.features.security.lifecycle.registration.models import User

        return User.objects.filter(company_id=company_id, is_active=True).count()

    def list_active_entity_ids(self, company_id: str) -> list[uuid.UUID]:
        from client.features.security.lifecycle.registration.models import User

        return list(
            User.objects.filter(company_id=company_id, is_active=True)
            .order_by('id')
            .values_list('id', flat=True)
        )

    def protected_entity_ids(self, company_id: str) -> set[uuid.UUID]:
        from client.features.security.lifecycle.registration.models import User

        ids = User.objects.filter(
            company_id=company_id,
            is_active=True,
            rol__name=ADMIN_ROLE_NAME,
        ).values_list('id', flat=True)
        return set(ids)

    def deactivate(self, entity_id: uuid.UUID, company_id: str) -> None:
        from client.features.security.lifecycle.registration.models import User

        updated = User.objects.filter(
            id=entity_id,
            company_id=company_id,
            is_active=True,
        ).update(is_active=False)
        if updated == 0:
            raise ValueError(f'User {entity_id} not found or already inactive')


def register_quota_adapters() -> None:
    enforcement_registry.register(CompanyUsersQuotaAdapter())
