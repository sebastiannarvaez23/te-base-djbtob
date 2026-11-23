#!/usr/bin/env python3
"""Phase 5 strangler: wire base core flags/tasks/realtime to necore.

IMPORTANT: This script writes the *current* hand-tuned host adapters.
Do not replace with naive re-exports — FlagContext must keep geo labels,
BaseTask must report incidents via ``core.tasks.incident_port``, and
``redis_lock`` must use ``caches`` from this module so tests can patch it.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / 'core'


def w(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    print('wrote', path.relative_to(ROOT))


def shim_flags() -> None:
    w(
        CORE / 'flags' / '__init__.py',
        '''"""Release flags — portable evaluator from necore; django store stays in platform."""
from __future__ import annotations

from necore.flags import (  # noqa: F401
    FakeFlagStore,
    FlagDefinition,
    FlagEvaluator,
    FlagKeys,
    FlagScope,
    FlagStatus,
    FlagType,
    IFlagStore,
    IScopeMatcher,
    ScopeMatcherRegistry,
    ScopeType,
    build_default_registry,
    is_enabled,
)
from necore.flags import set_flag_store_factory

from .config import get_flag_store  # product factory (django | fake)
from .domain.schemas import FlagContext

# Ensure necore.is_enabled default path uses base factory when hosts call necore directly.
set_flag_store_factory(get_flag_store)

__all__ = [
    'is_enabled',
    'get_flag_store',
    'FlagKeys',
    'FlagContext',
    'FlagDefinition',
    'FlagScope',
    'FlagStatus',
    'FlagType',
    'ScopeType',
    'IFlagStore',
    'IScopeMatcher',
    'FlagEvaluator',
    'FakeFlagStore',
    'ScopeMatcherRegistry',
    'build_default_registry',
    'set_flag_store_factory',
]
''',
    )
    w(
        CORE / 'flags' / 'config.py',
        '''"""Factory del store de release flags (base host adapter)."""
from __future__ import annotations

from django.conf import settings

from necore.flags.domain.interfaces import IFlagStore
from necore.flags.infrastructure.fake_store import FakeFlagStore


def _provider_name(override: str | None = None) -> str:
    return (override or getattr(settings, 'FLAG_STORE', 'django')).lower()


def get_flag_store(provider: str | None = None) -> IFlagStore:
    name = _provider_name(provider)
    if name == 'django':
        from platform.features.release.feature_flag.feature_flag.infrastructure.flag_store import (
            CachedDjangoFlagStore,
        )
        return CachedDjangoFlagStore()
    return FakeFlagStore()
''',
    )
    w(
        CORE / 'flags' / 'domain' / 'schemas.py',
        '''"""Base FlagContext — portable fields from necore + geo resolution via location helpers."""
from __future__ import annotations

from typing import Optional

from necore.flags.domain.schemas import (  # noqa: F401
    FlagDefinition,
    FlagScope,
    _empty_to_none,
)
from necore.flags.domain.schemas import FlagContext as _FlagContext


class FlagContext(_FlagContext):
    @classmethod
    def from_request(cls, request) -> FlagContext:
        company = getattr(request, 'tenant', None)
        user = getattr(request, 'user', None)

        company_id = country = state = city = None
        if company is not None:
            raw_id = getattr(company, 'id', None)
            company_id = _empty_to_none(str(raw_id) if raw_id is not None else None)
            from core.location import entity_location_labels

            country_name, state_name, city_name = entity_location_labels(company)
            country = _empty_to_none(country_name)
            state = _empty_to_none(state_name)
            city = _empty_to_none(city_name)

        user_id = None
        if user is not None and getattr(user, 'is_authenticated', False):
            raw_uid = getattr(user, 'id', None)
            if raw_uid is not None:
                user_id = _empty_to_none(str(raw_uid))

        return cls(
            company_id=company_id,
            user_id=user_id,
            country=country,
            state=state,
            city=city,
        )


__all__ = ['FlagContext', 'FlagDefinition', 'FlagScope', '_empty_to_none']
''',
    )
    for rel, dotted in [
        ('domain/enums.py', 'necore.flags.domain.enums'),
        ('domain/interfaces.py', 'necore.flags.domain.interfaces'),
        ('application/evaluator.py', 'necore.flags.application.evaluator'),
        ('infrastructure/fake_store.py', 'necore.flags.infrastructure.fake_store'),
        ('scopes/base.py', 'necore.flags.scopes.base'),
        ('scopes/company.py', 'necore.flags.scopes.company'),
        ('scopes/user.py', 'necore.flags.scopes.user'),
        ('scopes/country.py', 'necore.flags.scopes.country'),
        ('scopes/state.py', 'necore.flags.scopes.state'),
        ('scopes/city.py', 'necore.flags.scopes.city'),
        ('scopes/registry.py', 'necore.flags.scopes.registry'),
        ('scopes/__init__.py', 'necore.flags.scopes'),
        ('keys.py', 'necore.flags.keys'),
    ]:
        w(
            CORE / 'flags' / rel,
            f'"""Strangler shim — implementation lives in ``{dotted}``."""\n'
            f'from {dotted} import *  # noqa: F401,F403\n',
        )


def shim_tasks() -> None:
    w(
        CORE / 'tasks' / 'base.py',
        '''"""Task base classes — portable BaseTask from necore; TenantTask stays in the base."""
from __future__ import annotations

from contextlib import contextmanager

from django.core.cache import caches  # noqa: F401 — patched by tests on this module
from django_tenants.utils import schema_context

from necore.ids import uuid7
from necore.tasks.base import BaseTask as _NeBaseTask
from necore.tasks.base import RetryableTaskError, set_task_trace_hooks  # noqa: F401


class BaseTask(_NeBaseTask):
    """Base task — incident reporting goes through ``core.tasks.incident_port``."""

    def _report_incident(self, exc, task_id, kwargs, einfo):
        try:
            from core.task_trace import get_task_meta, peek_task_logs
            from core.tasks.incident_port import report_task_incident

            meta = get_task_meta()
            schema_name = meta.get('schema_name') or ''
            if not schema_name and isinstance(kwargs, dict):
                schema_name = str(kwargs.get('schema_name') or '')
            tb = ''
            if einfo is not None:
                tb = getattr(einfo, 'traceback', None) or str(einfo)
            report_task_incident(
                task_id=str(task_id or ''),
                task_name=self.name or '',
                exc=exc,
                traceback_text=tb,
                task_logs=peek_task_logs(),
                schema_name=schema_name,
            )
        except Exception as report_exc:
            import logging

            logging.getLogger('app.tasks').warning(
                'task_incident_report_failed task=%s id=%s error=%s',
                self.name,
                task_id,
                report_exc,
                extra={'task_id': task_id, 'task_name': self.name},
            )


@contextmanager
def redis_lock(key: str, ttl_seconds: int = 300):
    """SETNX lock; uses ``caches`` from this module so base tests can patch it."""
    cache = caches['auth']
    full_key = f'lock:{key}'
    token = uuid7().hex
    acquired = cache.add(full_key, token, timeout=ttl_seconds)
    try:
        yield acquired
    finally:
        if acquired and cache.get(full_key) == token:
            cache.delete(full_key)


class TenantTask(BaseTask):
    """Base for tasks that operate inside a tenant schema."""

    abstract = True

    def __call__(self, *args, **kwargs):
        schema = kwargs.pop('schema_name', None)
        if schema is None:
            return super().__call__(*args, **kwargs)
        with schema_context(schema):
            return super().__call__(*args, **kwargs)


def _wire_task_trace() -> None:
    from core.task_trace import (
        drain_task_logs,
        get_task_meta,
        peek_task_logs,
        start_task_capture,
    )

    set_task_trace_hooks(
        start_capture=start_task_capture,
        drain_logs=drain_task_logs,
        peek_logs=peek_task_logs,
        get_task_meta=get_task_meta,
    )


_wire_task_trace()

__all__ = [
    'BaseTask',
    'RetryableTaskError',
    'TenantTask',
    'redis_lock',
    'set_task_trace_hooks',
]
''',
    )
    for rel, dotted in [
        ('compensation.py', 'necore.tasks.compensation'),
        ('incident_port.py', 'necore.tasks.incident_port'),
        ('progress_port.py', 'necore.tasks.progress_port'),
        ('run_context.py', 'necore.tasks.run_context'),
    ]:
        w(
            CORE / 'tasks' / rel,
            f'"""Strangler shim — implementation lives in ``{dotted}``."""\n'
            f'from {dotted} import *  # noqa: F401,F403\n',
        )


def shim_realtime() -> None:
    w(
        CORE / 'realtime' / 'envelope.py',
        '''"""Strangler shim — implementation lives in ``necore.realtime.envelope``."""
from necore.realtime.envelope import *  # noqa: F401,F403
''',
    )


def main() -> None:
    shim_flags()
    shim_tasks()
    shim_realtime()
    print('base Phase 5 shims applied (hand-tuned host adapters preserved)')


if __name__ == '__main__':
    main()
