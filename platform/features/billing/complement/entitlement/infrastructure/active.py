"""Active complement licenses used by the access ceiling.

One query per company for functionality licenses and one for module
licenses. Callers cache the feature keys in Redis.
"""
from __future__ import annotations

from collections import defaultdict

from django.db.models import Q
from django.utils import timezone

from platform.features.billing.complement.entitlement.models import CompanyComplement
from platform.features.security.access.functionalities.models import Functionality


def _open(qs):
    now = timezone.now()
    return qs.filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))


def _functionality_qs():
    return _open(CompanyComplement.objects.filter(
        status=CompanyComplement.Status.ACTIVE,
        functionality__is_active=True,
        functionality__offering='complement',
        functionality__module__is_active=True,
        functionality__module__section__is_active=True,
    ))


def _module_qs():
    return _open(CompanyComplement.objects.filter(
        status=CompanyComplement.Status.ACTIVE,
        module__isnull=False,
        module__is_active=True,
        module__offering='complement',
        module__section__is_active=True,
    ))


def _keys_by_module(module_ids) -> dict:
    grouped: dict = defaultdict(set)
    if not module_ids:
        return grouped
    rows = Functionality.objects.filter(
        module_id__in=module_ids,
        is_active=True,
    ).values_list('module_id', 'key')
    for module_id, key in rows:
        if key:
            grouped[module_id].add(key)
    return grouped


def _read_complement_cache(company_id: str):
    try:
        from core.access.subscription import SubscriptionCache
        return SubscriptionCache.get_complements(company_id)
    except Exception:
        return None


def _write_complement_cache(company_id: str, keys: set[str], modules: set[str]) -> None:
    try:
        from core.access.subscription import SubscriptionCache
        SubscriptionCache.set_complements(company_id, keys, modules)
    except Exception:
        return None


def active_complement_access(company_id: str) -> tuple[set[str], set[str]]:
    """Feature keys and module codes licensed to the company right now.

    The snapshot lives in the access cache and is dropped with the rest of
    the company subscription cache when a license is granted or revoked.
    """
    company_id = str(company_id)
    cached = _read_complement_cache(company_id)
    if cached is not None:
        return cached
    keys, modules = _load_active_complement_access(company_id)
    _write_complement_cache(company_id, keys, modules)
    return keys, modules


def _load_active_complement_access(company_id: str) -> tuple[set[str], set[str]]:
    keys: set[str] = set()
    modules: set[str] = set()
    for key, module_code in _functionality_qs().filter(company_id=company_id).values_list(
        'functionality__key',
        'functionality__module__code',
    ):
        if key:
            keys.add(key)
        if module_code:
            modules.add(module_code)

    module_rows = list(_module_qs().filter(company_id=company_id).values_list('module_id', 'module__code'))
    keys_by_module = _keys_by_module({module_id for module_id, _code in module_rows})
    for module_id, module_code in module_rows:
        if module_code:
            modules.add(module_code)
        keys.update(keys_by_module.get(module_id, set()))
    return keys, modules


def active_complement_keys_by_company() -> dict[str, set[str]]:
    """All active complement keys grouped by company, for cache warmup."""
    grouped: dict[str, set[str]] = defaultdict(set)
    for company_id, key in _functionality_qs().values_list('company_id', 'functionality__key'):
        if key:
            grouped[str(company_id)].add(key)

    module_rows = list(_module_qs().values_list('company_id', 'module_id'))
    keys_by_module = _keys_by_module({module_id for _company_id, module_id in module_rows})
    for company_id, module_id in module_rows:
        grouped[str(company_id)].update(keys_by_module.get(module_id, set()))
    return grouped
