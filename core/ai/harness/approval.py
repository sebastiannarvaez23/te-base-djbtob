"""Aprobación humana mid-run (HITL) vía Redis/cache + Event in-process."""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Literal, Optional

from django.core.cache import caches
from django.db import connection

logger = logging.getLogger('app.ai')

_CACHE_ALIAS = 'access'
_KEY_PREFIX = 'ai:run:approval'
_DEFAULT_TTL = 600
Decision = Literal['approved', 'denied']

# In-process waiters (same worker that runs the agent thread).
_local_events: dict[str, threading.Event] = {}
_local_decisions: dict[str, Decision] = {}
_local_lock = threading.Lock()


def _cache():
    try:
        return caches[_CACHE_ALIAS]
    except Exception:
        return None


def _schema_name() -> str:
    try:
        return getattr(connection, 'schema_name', '') or ''
    except Exception:
        return ''


def _key(
    run_id: uuid.UUID,
    *,
    schema: str = '',
    user_id: uuid.UUID | str | None = None,
) -> str:
    sch = (schema or _schema_name() or 'unknown').strip() or 'unknown'
    uid = str(user_id) if user_id else 'anon'
    return f'{_KEY_PREFIX}:{sch}:{uid}:{run_id}'


def _local_id(
    run_id: uuid.UUID,
    *,
    schema: str = '',
    user_id: uuid.UUID | str | None = None,
) -> str:
    return _key(run_id, schema=schema, user_id=user_id)


class RunApprovalStore:
    """Publica/espera approve|deny para un AgentRun (scoped por tenant+user)."""

    def __init__(
        self,
        *,
        ttl_seconds: int = _DEFAULT_TTL,
        schema: str = '',
        user_id: uuid.UUID | str | None = None,
    ):
        self.ttl_seconds = ttl_seconds
        self.schema = schema or _schema_name()
        self.user_id = user_id

    def _rid(self, run_id: uuid.UUID) -> str:
        return _local_id(run_id, schema=self.schema, user_id=self.user_id)

    def _ckey(self, run_id: uuid.UUID) -> str:
        return _key(run_id, schema=self.schema, user_id=self.user_id)

    def begin_wait(self, run_id: uuid.UUID) -> threading.Event:
        rid = self._rid(run_id)
        with _local_lock:
            ev = threading.Event()
            _local_events[rid] = ev
            _local_decisions.pop(rid, None)
        cache = _cache()
        if cache is not None:
            try:
                cache.delete(self._ckey(run_id))
            except Exception as exc:
                logger.debug('approval begin clear failed: %s', exc)
        return ev

    def resolve(self, run_id: uuid.UUID, decision: Decision) -> None:
        rid = self._rid(run_id)
        with _local_lock:
            _local_decisions[rid] = decision
            ev = _local_events.get(rid)
            if ev is not None:
                ev.set()
        cache = _cache()
        if cache is not None:
            try:
                cache.set(self._ckey(run_id), decision, timeout=self.ttl_seconds)
            except Exception as exc:
                logger.debug('approval resolve failed: %s', exc)

    def wait(
        self,
        run_id: uuid.UUID,
        *,
        timeout_s: float = 120.0,
        cancel_check=None,
    ) -> Optional[Decision]:
        rid = self._rid(run_id)
        with _local_lock:
            ev = _local_events.get(rid)
        if ev is None:
            ev = self.begin_wait(run_id)

        deadline = timeout_s
        step = 0.25
        elapsed = 0.0
        while elapsed < deadline:
            if cancel_check and cancel_check():
                return None
            if ev.wait(timeout=step):
                with _local_lock:
                    return _local_decisions.get(rid)
            cache = _cache()
            if cache is not None:
                try:
                    raw = cache.get(self._ckey(run_id))
                    if raw in ('approved', 'denied'):
                        return raw  # type: ignore[return-value]
                except Exception:
                    pass
            elapsed += step
        return None

    def clear(self, run_id: uuid.UUID) -> None:
        rid = self._rid(run_id)
        with _local_lock:
            _local_events.pop(rid, None)
            _local_decisions.pop(rid, None)
        cache = _cache()
        if cache is not None:
            try:
                cache.delete(self._ckey(run_id))
            except Exception as exc:
                logger.debug('approval clear failed: %s', exc)
