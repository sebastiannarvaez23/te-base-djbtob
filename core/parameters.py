"""
core/parameters.py
──────────────────
Facade for reading global platform parameters from anywhere in the system.

Usage:
    from core.parameters import get_parameter

    max_retries = get_parameter('MAX_LOGIN_RETRIES')          # → int
    is_2fa = get_parameter('DOUBLE_FA_AUTH')                  # → bool

Hot-path values are cached briefly in the ``access`` Redis cache
(shared across workers) to avoid a PostgreSQL hit on every request.
"""

from __future__ import annotations

import json
import logging

from django.core.cache import caches

logger = logging.getLogger('app.parameters')

_CASTERS = {
    'STRING': str,
    'INT': int,
    'DECIMAL': float,
    'BOOL': lambda v: v.lower() in ('true', '1', 'yes'),
    'JSON': json.loads,
}

_CACHE_TTL_SECONDS = 30
_CACHE_KEY_PREFIX = 'param:v1:'
_MISS = object()


def _cache():
    return caches['access']


def _cache_key(code: str) -> str:
    return f'{_CACHE_KEY_PREFIX}{code}'


def clear_parameter_cache(code: str | None = None) -> None:
    """Drop cached parameter value(s). Best-effort; never raises."""
    try:
        if code:
            _cache().delete(_cache_key(code))
    except Exception as exc:
        logger.warning('Failed to clear parameter cache: %s', exc)


def get_parameter(code: str, default=None):
    """Return the cast value of a global parameter, or *default* if missing / inactive.

    This function is safe to call from any layer (platform or client).
    It never raises; on any error it returns *default* and logs a warning.
    """
    key = _cache_key(code)
    try:
        cached = _cache().get(key, _MISS)
        if cached is not _MISS:
            if cached is None:
                return default
            value, data_type = cached
            caster = _CASTERS.get(data_type, str)
            return caster(value)
    except Exception as exc:
        logger.warning('Parameter cache read failed for %s: %s', code, exc)

    try:
        from platform.features.configuration.parameters.parameter.models import Parameter
        param = (
            Parameter.objects
            .filter(code=code, is_active=True)
            .values('value', 'data_type')
            .first()
        )
        if param is None:
            try:
                _cache().set(key, None, _CACHE_TTL_SECONDS)
            except Exception:
                pass
            return default
        try:
            _cache().set(key, (param['value'], param['data_type']), _CACHE_TTL_SECONDS)
        except Exception:
            pass
        caster = _CASTERS.get(param['data_type'], str)
        return caster(param['value'])
    except Exception as exc:
        logger.warning('Failed to read parameter %s: %s', code, exc)
        return default
