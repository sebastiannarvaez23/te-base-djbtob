"""Stores de idempotencia (memoria y Redis)."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from django.core.cache import caches

from core.integrations.domain.interfaces import IIdempotencyStore

logger = logging.getLogger('app.integrations')


class MemoryIdempotencyStore(IIdempotencyStore):
    """Store en memoria para tests unitarios."""

    def __init__(self):
        self._data: dict[str, dict[str, Any]] = {}

    def _key(self, scope: str, key: str) -> str:
        return f'{scope}:{key}'

    def get(self, scope: str, key: str) -> Optional[dict[str, Any]]:
        return self._data.get(self._key(scope, key))

    def put(
        self,
        scope: str,
        key: str,
        payload: dict[str, Any],
        *,
        ttl_seconds: int = 86400,
    ) -> None:
        del ttl_seconds
        self._data[self._key(scope, key)] = dict(payload)


class RedisIdempotencyStore(IIdempotencyStore):
    """Store Redis con degradación best-effort si la caché no está disponible."""

    def __init__(self, cache_alias: str = 'default'):
        self._cache_alias = cache_alias

    def _cache_key(self, scope: str, key: str) -> str:
        return f'integrations:idempotency:{scope}:{key}'

    def get(self, scope: str, key: str) -> Optional[dict[str, Any]]:
        try:
            cache = caches[self._cache_alias]
            raw = cache.get(self._cache_key(scope, key))
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as exc:
            logger.warning('idempotency get failed (degraded): %s', exc)
            return None

    def put(
        self,
        scope: str,
        key: str,
        payload: dict[str, Any],
        *,
        ttl_seconds: int = 86400,
    ) -> None:
        try:
            cache = caches[self._cache_alias]
            cache.set(
                self._cache_key(scope, key),
                json.dumps(payload),
                timeout=ttl_seconds,
            )
        except Exception as exc:
            logger.warning('idempotency put failed (degraded): %s', exc)
