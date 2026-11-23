"""Redis-backed store for short-lived 2FA login challenges.

Shared by platform admin and client tenant auth. One live challenge per
user (schema-scoped). Issuing a new challenge deletes the previous one
so only the latest OTP can succeed.

The OTP itself is never stored — only an HMAC of ``challenge_id:otp``.
Attempt counters live in a separate integer key so ``INCR`` is atomic.
"""

from __future__ import annotations

import json
from typing import Optional

from django.core.cache import caches

_PREFIX = '2fa_challenge:'
_USER_PREFIX = '2fa_user:'
_ATTEMPTS_PREFIX = '2fa_attempts:'


def _cache():
    return caches['auth']


def _challenge_key(challenge_id: str) -> str:
    return f'{_PREFIX}{challenge_id}'


def _user_key(schema_name: str, user_id) -> str:
    return f'{_USER_PREFIX}{schema_name}:{user_id}'


def _attempts_key(challenge_id: str) -> str:
    return f'{_ATTEMPTS_PREFIX}{challenge_id}'


def put(challenge_id: str, payload: dict, ttl_seconds: int) -> None:
    _cache().set(_challenge_key(challenge_id), json.dumps(payload), timeout=ttl_seconds)


def get(challenge_id: str) -> Optional[dict]:
    raw = _cache().get(_challenge_key(challenge_id))
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def get_active_id(schema_name: str, user_id) -> Optional[str]:
    value = _cache().get(_user_key(schema_name, user_id))
    if not value:
        return None
    return str(value)


def replace_for_user(
    schema_name: str,
    user_id,
    challenge_id: str,
    payload: dict,
    ttl_seconds: int,
) -> None:
    """Persist ``challenge_id`` as the only live challenge for this user."""
    cache = _cache()
    ukey = _user_key(schema_name, user_id)
    ttl = max(int(ttl_seconds), 1)
    old_id = cache.get(ukey)
    if old_id and str(old_id) != challenge_id:
        delete(str(old_id))
        cache.delete(_attempts_key(challenge_id))
    elif not old_id:
        cache.delete(_attempts_key(challenge_id))
    cache.set(ukey, challenge_id, timeout=ttl)
    put(challenge_id, payload, ttl)


def incr_attempts(challenge_id: str, ttl_seconds: int) -> int:
    """Atomically count a failed OTP. Returns the new total."""
    cache = _cache()
    key = _attempts_key(challenge_id)
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


def get_attempts(challenge_id: str) -> int:
    raw = _cache().get(_attempts_key(challenge_id))
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def delete(challenge_id: str) -> None:
    cache = _cache()
    payload = get(challenge_id) or {}
    cache.delete(_challenge_key(challenge_id))
    cache.delete(_attempts_key(challenge_id))
    schema_name = payload.get('schema_name')
    user_id = payload.get('user_id')
    if schema_name and user_id is not None:
        ukey = _user_key(str(schema_name), user_id)
        if str(cache.get(ukey) or '') == challenge_id:
            cache.delete(ukey)
