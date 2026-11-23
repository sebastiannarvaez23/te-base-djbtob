"""Refresh token service backed by Redis.

Refresh tokens are opaque random strings stored hashed in the 'auth'
Redis cache.  They are the *only* way to obtain a new access token
after it expires.

Key schema
----------
  rt:{user_type}:{user_id}:{token_id}

  - user_type : 'admin' | 'client'
  - user_id   : str(UUID)
  - token_id  : first 16 hex chars of the SHA-256 hash (collision-safe
                 enough given the random token space)

Value
-----
  JSON string:
    {
      "hash":             "<full sha256 hex>",
      "user_id":          "<uuid>",
      "user_type":        "admin" | "client",
      "schema_name":      "<tenant schema>",
      "ip_address":       "<ip>",
      "user_agent":       "<ua>",
      "created_at":       "<iso>",
      "expires_at":       "<iso>",
      "last_activity_at": "<iso>",
      "remember_me":      true | false
    }
"""
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from django.conf import settings
from django.core.cache import caches


def _cache():
    return caches['auth']


def get_refresh_ttl_days(user_type: str = 'client') -> int:
    """Read REF_TOKEN_DURATION (days) from the matching parameter catalog.

    ``admin`` → admin catalog; everything else → client/runtime catalog.
    Both paths use cached facades (no direct PostgreSQL on the hot path).
    Returns the fallback value (14 days) if the parameter does not exist
    or is inactive.
    """
    try:
        if user_type == 'admin':
            from core.admin_parameters import get_admin_parameter
            value = get_admin_parameter('REF_TOKEN_DURATION', default=None)
        else:
            from core.parameters import get_parameter
            value = get_parameter('REF_TOKEN_DURATION', default=None)
        if value is None:
            return 14
        return int(value)
    except Exception:
        return 14  # 14-day fallback


# Browser-session logins (Remember me off). Chrome may restore session
# cookies after a crash; this Redis cap is the real logout bound.
SESSION_REFRESH_TTL_SECONDS = 12 * 3600


def _ttl_seconds(user_type: str = 'client') -> int:
    return get_refresh_ttl_days(user_type) * 86400


def refresh_ttl_seconds(*, remember_me: bool, user_type: str = 'client') -> int:
    """TTL for a newly minted refresh token.

    Remember-me sessions last ``REF_TOKEN_DURATION`` days. Unchecked
    logins last at most 12 hours so a stolen session cookie cannot be
    replayed for the full persistent window.
    """
    persistent = max(_ttl_seconds(user_type), 1)
    if remember_me:
        return persistent
    return min(SESSION_REFRESH_TTL_SECONDS, persistent)


def record_is_remembered(record: dict | None) -> bool:
    """Sessions minted before this flag existed were all persistent."""
    if not record:
        return True
    return bool(record.get('remember_me', True))


def _key(user_type: str, user_id: str, token_id: str) -> str:
    return f'rt:{user_type}:{user_id}:{token_id}'


def _index_key(user_type: str, token_id: str) -> str:
    """Índice inverso ``token_id`` → clave lógica del registro.

    El ``token_id`` se deriva del hash del token crudo, así que en validación
    lo conocemos sin conocer el ``user_id``. Este índice permite resolver el
    registro con un GET O(1) en vez de un ``SCAN`` sobre todo el keyspace.

    Nota: ``rtid:`` NO colisiona con los patrones ``rt:*`` (glob de Redis exige
    el ``:`` literal), por lo que los listados que escanean ``rt:*`` nunca
    recogen estas claves de índice.
    """
    return f'rtid:{user_type}:{token_id}'


# django-redis stores keys as: {KEY_PREFIX}:{VERSION}:{cache_key}
# With our config (KEY_PREFIX='auth', VERSION=1), the full prefix is 'auth:1:'.
_REDIS_KEY_PREFIX = 'auth:1:'


def _key_pattern(user_type: str, user_id: str) -> str:
    return f'{_REDIS_KEY_PREFIX}rt:{user_type}:{user_id}:*'


def _all_pattern() -> str:
    return f'{_REDIS_KEY_PREFIX}rt:*'


# ── Public API ───────────────────────────────────────────────────────────────


def generate_raw_token() -> str:
    """Generate a cryptographically secure random refresh token."""
    return secrets.token_urlsafe(64)


def hash_token(raw_token: str) -> str:
    """SHA-256 hash of the raw token (hex digest)."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def store(
    raw_token: str,
    user_id,
    user_type: str,
    schema_name: str = 'public',
    ip_address: str = '',
    user_agent: str = '',
    *,
    ttl_seconds: int | None = None,
    remember_me: bool = True,
    last_activity_at: str | None = None,
) -> tuple[str, str]:
    """Hash and store a refresh token in Redis.

    Returns a tuple of (raw_token, token_id).  The raw_token is placed
    in the cookie; the token_id is embedded in the JWT for session
    validation on every request.

    ``remember_me`` defaults to True so admin login and legacy callers
    keep persistent cookies. Client login passes the checkbox explicitly.
    """
    h = hash_token(raw_token)
    token_id = h[:16]
    now = datetime.utcnow()
    ttl = (
        max(int(ttl_seconds), 1)
        if ttl_seconds is not None
        else _ttl_seconds(user_type)
    )
    remembered = bool(remember_me)
    activity = last_activity_at if isinstance(last_activity_at, str) and last_activity_at else now.isoformat()

    data = {
        'hash': h,
        'user_id': str(user_id),
        'user_type': user_type,
        'schema_name': schema_name,
        'ip_address': ip_address or '',
        'user_agent': user_agent or '',
        'created_at': now.isoformat(),
        'expires_at': (now + timedelta(seconds=ttl)).isoformat(),
        'last_activity_at': activity,
        'remember_me': remembered,
    }

    cache = _cache()
    record_key = _key(user_type, str(user_id), token_id)
    cache.set(record_key, json.dumps(data), timeout=ttl)
    # Índice inverso para resolución O(1) en validate()/revoke() sin SCAN.
    # Mismo TTL: si el registro caduca, el índice caduca con él.
    cache.set(_index_key(user_type, token_id), record_key, timeout=ttl)
    return raw_token, token_id


def validate(raw_token: str, expected_type: str) -> Optional[dict]:
    """Validate a raw refresh token against Redis.

    Returns the stored record dict if valid, None otherwise.
    """
    h = hash_token(raw_token)
    token_id = h[:16]

    client = _get_redis_client()
    if client is None:
        return None

    cache = _cache()

    # Fast path O(1): el índice inverso nos da la clave exacta del registro
    # sin recorrer el keyspace.
    record_key = cache.get(_index_key(expected_type, token_id))
    if record_key:
        record = _read_record(cache, record_key)
        if record is not None and record.get('hash') == h:
            return record

    # Fallback: índice ausente (token creado antes de existir el índice, o
    # una escritura de índice que falló). Se recurre al SCAN por token_id.
    pattern = f'{_REDIS_KEY_PREFIX}rt:{expected_type}:*:{token_id}'
    for key in _scan_keys(client, pattern):
        record = _read_record(cache, _strip_prefix(key))
        if record is not None and record.get('hash') == h:
            return record

    return None


def read_session(user_type: str, user_id: str, token_id: str) -> Optional[dict]:
    """Return one refresh record, or None when the session is gone."""
    if not token_id:
        return None
    return _read_record(_cache(), _key(user_type, str(user_id), token_id))


def revoke_session(user_type: str, user_id: str, token_id: str) -> bool:
    """Drop one session by the id embedded in the access token."""
    if not token_id:
        return False
    return revoke_by_session_key(_key(user_type, str(user_id), token_id))


# Skip Redis writes when activity was recorded moments ago.
_ACTIVITY_TOUCH_SECONDS = 30


def touch_session_activity(
    user_type: str,
    user_id: str,
    token_id: str,
    record: dict | None = None,
) -> bool:
    """Slide ``last_activity_at`` without extending the refresh TTL.

    Uses Redis ``SET … XX`` so a concurrent revoke/logout cannot resurrect
    the session key. Returns True when the write landed.

    The refresh lifetime stays ``REF_TOKEN_DURATION`` / the remember-me cap.
    Inactivity is a separate clock inside that window.
    """
    if not token_id:
        return False
    cache = _cache()
    key = _key(user_type, str(user_id), token_id)
    current = record if record is not None else _read_record(cache, key)
    if not current:
        return False
    now = datetime.utcnow()
    previous = parse_utc_timestamp(current.get('last_activity_at'))
    if previous is not None and (now - previous).total_seconds() < _ACTIVITY_TOUCH_SECONDS:
        return False
    ttl = _remaining_ttl(key)
    if ttl is None:
        return False
    updated = {k: v for k, v in current.items() if k != 'session_key'}
    updated['last_activity_at'] = now.isoformat()
    return _set_existing_record(key, updated, ttl)


def session_exists(user_type: str, user_id: str, token_id: str) -> bool:
    """Check whether a refresh token session is still alive in Redis.

    Used by JWT access authentication to enforce immediate session kill:
    if the refresh token was revoked, the access token must be rejected
    even though its signature is still valid.
    """
    if not token_id:
        return False
    return _read_record(_cache(), _key(user_type, str(user_id), token_id)) is not None


def revoke(raw_token: str, user_type: str) -> bool:
    """Revoke (delete) a specific refresh token.

    Returns True if the token was found and deleted.
    """
    h = hash_token(raw_token)
    token_id = h[:16]

    client = _get_redis_client()
    if client is None:
        return False

    cache = _cache()

    # Fast path O(1) vía índice inverso; fallback a SCAN si no está.
    record_key = cache.get(_index_key(user_type, token_id))
    candidate_keys = (
        [record_key] if record_key
        else [
            _strip_prefix(k)
            for k in _scan_keys(client, f'{_REDIS_KEY_PREFIX}rt:{user_type}:*:{token_id}')
        ]
    )

    for cache_key in candidate_keys:
        record = _read_record(cache, cache_key)
        if record is not None and record.get('hash') == h:
            cache.delete(cache_key)
            cache.delete(_index_key(user_type, token_id))
            return True
    return False


def revoke_all_for_user(user_id, user_type: str) -> int:
    """Revoke all refresh tokens for a specific user.

    Returns the number of tokens revoked.
    """
    client = _get_redis_client()
    if client is None:
        return 0

    pattern = _key_pattern(user_type, str(user_id))
    keys = _scan_keys(client, pattern)
    if not keys:
        return 0

    client.delete(*keys)
    _delete_indexes_for(keys)
    return len(keys)


def revoke_others_for_user(user_id, user_type: str, keep_token_id: str) -> int:
    """Revoke every refresh token for the user except ``keep_token_id``.

    Used after minting a session under MULTI_SESSIONS=false so a concurrent
    login race cannot leave two live sessions.
    """
    if not keep_token_id:
        return revoke_all_for_user(user_id, user_type)

    client = _get_redis_client()
    if client is None:
        return 0

    keep_logical = _key(user_type, str(user_id), keep_token_id)
    pattern = _key_pattern(user_type, str(user_id))
    keys = [
        k for k in _scan_keys(client, pattern)
        if _strip_prefix(k) != keep_logical
    ]
    if not keys:
        return 0
    client.delete(*keys)
    _delete_indexes_for(keys)
    return len(keys)


def revoke_all_for_users(user_ids, user_type: str) -> int:
    """Revoke all refresh tokens for a list of users."""
    count = 0
    for uid in user_ids:
        count += revoke_all_for_user(uid, user_type)
    return count


def revoke_all() -> int:
    """Revoke ALL refresh tokens (admin + client)."""
    client = _get_redis_client()
    if client is None:
        return 0

    pattern = _all_pattern()
    keys = _scan_keys(client, pattern)
    if not keys:
        return 0

    client.delete(*keys)
    # Purga también todos los índices inversos de una vez.
    idx_keys = _scan_keys(client, f'{_REDIS_KEY_PREFIX}rtid:*')
    if idx_keys:
        client.delete(*idx_keys)
    return len(keys)


def list_all(user_type: str = None) -> list[dict]:
    """List all stored refresh token records.

    Optionally filter by user_type ('admin' or 'client').
    Returns list of record dicts.
    """
    client = _get_redis_client()
    if client is None:
        return []

    if user_type:
        pattern = f'{_REDIS_KEY_PREFIX}rt:{user_type}:*'
    else:
        pattern = _all_pattern()

    keys = _scan_keys(client, pattern)
    return _load_records([_strip_prefix(k) for k in keys])


def list_for_user(user_id, user_type: str) -> list[dict]:
    """List all refresh tokens for a specific user."""
    client = _get_redis_client()
    if client is None:
        return []

    pattern = _key_pattern(user_type, str(user_id))
    keys = _scan_keys(client, pattern)
    return _load_records([_strip_prefix(k) for k in keys])


def revoke_by_session_key(session_key: str) -> bool:
    """Revoke a refresh token by its cache key (used by session management)."""
    cache = _cache()
    deleted = cache.delete(session_key)
    # Limpia el índice inverso asociado (session_key = rt:type:uid:token_id).
    parts = session_key.split(':')
    if len(parts) >= 4 and parts[0] == 'rt':
        cache.delete(_index_key(parts[1], parts[-1]))
    return deleted


# ── Internal helpers ─────────────────────────────────────────────────────────


def parse_utc_timestamp(raw) -> Optional[datetime]:
    """Parse an ISO timestamp to naive UTC, or None when missing/invalid."""
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _remaining_ttl(cache_key: str) -> Optional[int]:
    """Seconds left on a refresh record. None when missing or without expiry."""
    client = _get_redis_client()
    if client is None:
        return None
    try:
        ttl = int(client.ttl(f'{_REDIS_KEY_PREFIX}{cache_key}'))
    except (TypeError, ValueError):
        return None
    # Redis: -2 missing, -1 no expiry, >0 seconds remaining.
    if ttl <= 0:
        return None
    return ttl


def _set_existing_record(cache_key: str, data: dict, ttl: int) -> bool:
    """Write a refresh record only if the Redis key still exists (``XX``).

    Values must be encoded the same way as ``cache.set`` (django-redis
    pickle). Writing raw JSON breaks ``cache.get`` with UnpicklingError.
    """
    cache = _cache()
    client = _get_redis_client()
    if client is None:
        return False
    try:
        redis_client = cache.client
        full_key = redis_client.make_key(cache_key)
        encoded = redis_client.encode(json.dumps(data))
        return bool(client.set(full_key, encoded, ex=int(ttl), xx=True))
    except Exception:
        return False


def _get_redis_client():
    """Get the underlying Redis client from the 'auth' cache."""
    try:
        cache = _cache()
        return cache.client.get_client()
    except Exception:
        return None


def _decode_record(raw_value):
    """Normaliza el valor almacenado a un dict (o None)."""
    if raw_value is None:
        return None
    if isinstance(raw_value, (bytes, bytearray)):
        try:
            raw_value = raw_value.decode('utf-8')
        except Exception:
            return None
    if isinstance(raw_value, str):
        try:
            return json.loads(raw_value)
        except (ValueError, TypeError):
            return None
    if isinstance(raw_value, dict):
        return raw_value
    return None


def _drop_corrupt_session_key(cache_key: str) -> None:
    """Delete a session key that django-redis can no longer decode."""
    try:
        _cache().delete(cache_key)
    except Exception:
        client = _get_redis_client()
        if client is None:
            return
        try:
            client.delete(f'{_REDIS_KEY_PREFIX}{cache_key}')
        except Exception:
            return


def _read_record(cache, cache_key: str):
    """Lee y decodifica un registro por su clave lógica (o None).

    Corrupt values (e.g. raw JSON written without pickle) are deleted so
    login / list_sessions can recover without a Redis flush.
    """
    try:
        return _decode_record(cache.get(cache_key))
    except Exception:
        pass
    # Heal path: value may be plain JSON from a buggy raw SET.
    client = _get_redis_client()
    if client is not None:
        try:
            raw = client.get(f'{_REDIS_KEY_PREFIX}{cache_key}')
            record = _decode_record(raw)
            if record is not None:
                ttl = _remaining_ttl(cache_key)
                if ttl is not None:
                    cache.set(cache_key, json.dumps(record), timeout=ttl)
                    return record
        except Exception:
            pass
    _drop_corrupt_session_key(cache_key)
    return None


def _load_records(cache_keys: list[str]) -> list[dict]:
    """Load session records one key at a time (safe with corrupt values).

    ``get_many`` aborts the whole batch on the first UnpicklingError, so
    we read per key via ``_read_record`` (heal or drop). Attaches
    ``session_key`` for session-kill operations.
    """
    if not cache_keys:
        return []
    cache = _cache()
    records = []
    for cache_key in cache_keys:
        record = _read_record(cache, cache_key)
        if record is None:
            continue
        record['session_key'] = cache_key
        records.append(record)
    return records


def _delete_indexes_for(full_keys: list) -> None:
    """Borra los índices inversos asociados a un lote de claves de registro.

    ``full_keys`` son claves crudas de Redis (con prefijo ``auth:1:``); de cada
    una se extrae user_type y token_id para reconstruir la clave de índice.
    """
    cache = _cache()
    for key in full_keys:
        logical = _strip_prefix(key)          # rt:type:uid:token_id
        parts = logical.split(':')
        if len(parts) >= 4 and parts[0] == 'rt':
            cache.delete(_index_key(parts[1], parts[-1]))


def _scan_keys(client, pattern: str) -> list:
    """SCAN Redis for keys matching a pattern. Returns list of byte/str keys."""
    keys = []
    cursor = 0
    while True:
        cursor, batch = client.scan(cursor=cursor, match=pattern, count=200)
        keys.extend(batch)
        if cursor == 0:
            break
    return keys


def _strip_prefix(key) -> str:
    """Strip the 'auth:' KEY_PREFIX added by django-redis to get the cache key.

    django-redis prepends KEY_PREFIX + ':1:' (version) to all keys.
    When we SCAN Redis we get the full Redis key; to use cache.get()
    we need the logical key without the prefix.
    """
    k = key.decode() if isinstance(key, bytes) else key
    # Full Redis key looks like: auth:1:rt:admin:uuid:tokenid
    # The cache key (what we pass to cache.get/set) is: rt:admin:uuid:tokenid
    # django-redis format: {KEY_PREFIX}:{VERSION}:{key}
    parts = k.split(':', 2)
    if len(parts) >= 3 and parts[0] == 'auth':
        return parts[2]  # skip 'auth' prefix and '1' version
    return k
