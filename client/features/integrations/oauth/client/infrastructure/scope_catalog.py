"""Scope catalog backed by the functionality catalog + core/access.

Grantable = active API functionalities ∩ tenant plan ∩ acting user's role,
the same rule ``HasSubscriptionAccess`` applies to every tenant endpoint.
"""
from __future__ import annotations

from typing import Iterable, Optional

from client.features.integrations.oauth.client.domain.interfaces import IIntegrationScopeCatalog
from client.features.integrations.oauth.client.domain.schemas import IntegrationScopeSchema
from core.access import AccessChecker
from core.access.role_cache import RoleFeatureCache
from platform.features.security.access.functionalities.domain.categories import API_CATEGORY
from platform.features.security.access.functionalities.models import Functionality


class AccessControlScopeCatalog(IIntegrationScopeCatalog):
    """Per-request catalog: ``user=None`` means no actor (token endpoint)."""

    def __init__(self, company, user=None):
        self._company = company
        self._user = user
        self._tenant_scopes: Optional[list[IntegrationScopeSchema]] = None

    def tenant_scopes(self) -> list[IntegrationScopeSchema]:
        if self._tenant_scopes is None:
            self._tenant_scopes = self._load_tenant_scopes()
        return self._tenant_scopes

    def grantable_scopes(self) -> list[IntegrationScopeSchema]:
        if self._user is None:
            return []
        scopes = self.tenant_scopes()
        role_keys = self._role_keys()
        if role_keys is None:
            return scopes
        return [scope for scope in scopes if scope.key in role_keys]

    def api_scope_keys(self, keys: Iterable[str]) -> set[str]:
        wanted = set(keys)
        if not wanted:
            return set()
        return set(
            Functionality.objects
            .filter(category=API_CATEGORY, key__in=wanted)
            .values_list('key', flat=True)
        )

    def _load_tenant_scopes(self) -> list[IntegrationScopeSchema]:
        if self._company is None:
            return []
        enabled = AccessChecker.enabled_features(self._company)
        if not enabled:
            return []
        rows = (
            Functionality.objects
            .filter(
                category=API_CATEGORY,
                key__in=enabled,
                is_active=True,
                module__is_active=True,
                module__section__is_active=True,
            )
            .select_related('module')
            .order_by('module__order', 'key')
        )
        return [
            IntegrationScopeSchema(
                key=row.key,
                label=row.label,
                module=row.module.code,
                module_name=row.module.name,
            )
            for row in rows
        ]

    def _role_keys(self) -> Optional[set[str]]:
        """Role grants; ``None`` when the user has no role (plan alone decides)."""
        rol = getattr(self._user, 'rol', None)
        role_id = getattr(self._user, 'rol_id', None) or getattr(rol, 'id', None)
        if not role_id:
            return None
        if rol is not None and not getattr(rol, 'is_active', True):
            return set()
        return RoleFeatureCache.get_or_load(str(role_id))
