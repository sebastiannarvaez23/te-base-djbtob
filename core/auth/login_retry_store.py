"""Cache-backed counter of consecutive failed password attempts.

Keys are schema-scoped so tenants / admin do not share lockout state.
``INCR`` is atomic; LocMem (tests) is handled the same way as the 2FA store.
"""

from __future__ import annotations

from django.core.cache import caches
from django.db import connection

from core.errors.retry_after import cache_retry_after

_PREFIX = 'login_fail:'


def _cache():
    return caches['auth']


def schema_name() -> str:
    return str(getattr(connection, 'schema_name', None) or 'public')


def _normalize(username: str) -> str:
    return (username or '').strip().lower()[:150]


def _key(schema: str, username: str) -> str:
    return f'{_PREFIX}{schema}:{_normalize(username)}'


def incr_failures(username: str, ttl_seconds: int, *, schema: str | None = None) -> int:
    """Atomically count a failed password. Returns the new total."""
    ident = _normalize(username)
    if not ident:
        return 0
    cache = _cache()
    key = _key(schema or schema_name(), ident)
    ttl = max(int(ttl_seconds), 1)
    try:
        return int(cache.incr(key))
    except ValueError:
        cache.add(key, 0, timeout=ttl)
        try:
            return int(cache.incr(key))
        except ValueError:
            cache.set(key, 1, timeout=ttl)
            return 1


def get_failures(username: str, *, schema: str | None = None) -> int:
    ident = _normalize(username)
    if not ident:
        return 0
    raw = _cache().get(_key(schema or schema_name(), ident))
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def refresh_ttl(username: str, count: int, ttl_seconds: int, *, schema: str | None = None) -> None:
    """Restart the lock window once the retry ceiling is hit."""
    ident = _normalize(username)
    if not ident:
        return
    cache = _cache()
    key = _key(schema or schema_name(), ident)
    ttl = max(int(ttl_seconds), 1)
    touch = getattr(cache, 'touch', None)
    if callable(touch) and touch(key, ttl):
        return
    cache.set(key, int(count), timeout=ttl)


def ttl_remaining(username: str, *, schema: str | None = None) -> int | None:
    ident = _normalize(username)
    if not ident:
        return None
    return cache_retry_after(_cache(), _key(schema or schema_name(), ident))


def clear_failures(username: str, *, schema: str | None = None) -> None:
    ident = _normalize(username)
    if not ident:
        return
    _cache().delete(_key(schema or schema_name(), ident))
