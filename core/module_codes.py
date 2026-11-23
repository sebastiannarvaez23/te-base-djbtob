"""Helpers to reconcile module code strings across catalog, roles and subscriptions."""

from __future__ import annotations

from typing import Iterable


def module_catalog_index() -> dict[str, str]:
    """Map ``module.code.lower()`` → canonical tenant ``Module.code`` (public schema)."""
    from platform.features.security.access.modules.models import Module

    return {m.code.lower(): m.code for m in Module.objects.all()}


def admin_module_catalog_index() -> dict[str, str]:
    """Map ``admin module.code.lower()`` → canonical ``AdminModule.code``."""
    from platform.features.security.access.roles.models import AdminModule

    return {m.code.lower(): m.code for m in AdminModule.objects.all()}


def canonicalize_module_codes(
    codes: Iterable[str],
    catalog: dict[str, str] | None = None,
) -> list[str]:
    """
    Resolve role/subscription code strings to the catalog casing, preserving order
    and dropping unknown codes.
    """
    index = catalog or module_catalog_index()
    seen: set[str] = set()
    resolved: list[str] = []
    for raw in codes:
        key = (raw or '').strip().lower()
        if not key:
            continue
        canonical = index.get(key)
        if canonical and canonical not in seen:
            seen.add(canonical)
            resolved.append(canonical)
    return resolved


def filter_codes_in_set_case_insensitive(codes: Iterable[str], allowed: set[str]) -> list[str]:
    """Keep codes whose lowercase form appears in ``allowed`` (also compared lowercased)."""
    allowed_lower = {(c or '').lower() for c in allowed}
    return [c for c in codes if c.lower() in allowed_lower]


def normalize_module_route(route: str | None) -> str:
    """Ensure sidebar routes are absolute paths for the SPA router."""
    raw = (route or '').strip()
    if not raw:
        return ''
    return raw if raw.startswith('/') else f'/{raw}'


def rename_module_code_in_grants(old_code: str, new_code: str) -> None:
    """Propagate a tenant catalog module code rename to subscriptions and role grants."""
    from django_tenants.utils import get_tenant_model, schema_context

    from client.features.security.lifecycle.registration.models import RolModule
    from platform.features.billing.subscription.subscription.models import SubscriptionModule

    if not old_code or not new_code or old_code == new_code:
        return

    SubscriptionModule.objects.filter(module_code=old_code).update(module_code=new_code)

    Tenant = get_tenant_model()
    for tenant in Tenant.objects.exclude(schema_name='public').iterator():
        with schema_context(tenant.schema_name):
            RolModule.objects.filter(module_code=old_code).update(module_code=new_code)


def rename_admin_module_code_in_grants(old_code: str, new_code: str) -> None:
    """Propagate an admin catalog module code rename to admin role grants."""
    from platform.features.security.access.roles.models import AdminRoleModule

    if not old_code or not new_code or old_code == new_code:
        return

    AdminRoleModule.objects.filter(module_code=old_code).update(module_code=new_code)

