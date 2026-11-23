"""Cancelación de AgentRun vía cache Redis (hot path) + Event in-process.

Blocking provider HTTP (e.g. OpenAI ``complete``) cannot be aborted mid-socket;
cancel is observed between stream chunks / agent loop steps. Prefer local Event
first; Redis is polled at most once per ``redis_poll_interval_s``.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Optional

from django.core.cache import caches
from django.db import connection

logger = logging.getLogger('app.ai')

_CACHE_ALIAS = 'access'
_KEY_PREFIX = 'ai:run:cancel'
_DEFAULT_TTL = 900  # 15 min — cubre un turno largo + cold start
_DEFAULT_REDIS_POLL_S = 0.5


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


class RunCancelStore:
    """Marca / consulta cancelación de un run (scoped por tenant+user)."""

    def __init__(
        self,
        *,
        ttl_seconds: int = _DEFAULT_TTL,
        schema: str = '',
        user_id: uuid.UUID | str | None = None,
        redis_poll_interval_s: float = _DEFAULT_REDIS_POLL_S,
    ):
        self.ttl_seconds = ttl_seconds
        self.schema = schema or _schema_name()
        self.user_id = user_id
        self.redis_poll_interval_s = max(0.05, float(redis_poll_interval_s))
        self._last_redis_at: dict[str, float] = {}
        self._last_redis_hit: dict[str, bool] = {}

    def _ckey(self, run_id: uuid.UUID) -> str:
        return _key(run_id, schema=self.schema, user_id=self.user_id)

    def request_cancel(self, run_id: uuid.UUID) -> None:
        cache = _cache()
        if cache is None:
            return
        try:
            cache.set(self._ckey(run_id), '1', timeout=self.ttl_seconds)
            self._last_redis_hit[str(run_id)] = True
        except Exception as exc:
            logger.debug('run cancel set failed: %s', exc)

    def is_cancelled(self, run_id: uuid.UUID) -> bool:
        rid = str(run_id)
        now = time.monotonic()
        last = self._last_redis_at.get(rid, 0.0)
        if now - last < self.redis_poll_interval_s:
            return bool(self._last_redis_hit.get(rid))
        self._last_redis_at[rid] = now
        cache = _cache()
        if cache is None:
            return False
        try:
            hit = bool(cache.get(self._ckey(run_id)))
            self._last_redis_hit[rid] = hit
            return hit
        except Exception as exc:
            logger.debug('run cancel get failed: %s', exc)
            return False

    def clear(self, run_id: uuid.UUID) -> None:
        rid = str(run_id)
        self._last_redis_at.pop(rid, None)
        self._last_redis_hit.pop(rid, None)
        cache = _cache()
        if cache is None:
            return
        try:
            cache.delete(self._ckey(run_id))
        except Exception as exc:
            logger.debug('run cancel clear failed: %s', exc)


def is_cancelled(
    *,
    run_id: Optional[uuid.UUID] = None,
    local: Optional[threading.Event] = None,
    store: Optional[RunCancelStore] = None,
) -> bool:
    """True si el Event local o la marca Redis piden abortar."""
    if local is not None and local.is_set():
        return True
    if run_id is not None:
        return (store or RunCancelStore()).is_cancelled(run_id)
    return False
