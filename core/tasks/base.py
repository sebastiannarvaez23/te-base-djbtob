"""Task base classes — portable BaseTask from necore; TenantTask stays in the base."""
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
