"""
core/admin_parameters.py
───────────────────────
Facade for reading admin-only parameters (public schema catalog).

Usage:
    from core.admin_parameters import get_admin_parameter

    max_retries = get_admin_parameter('MAX_LOGIN_RETRIES')  # → int
    is_2fa = get_admin_parameter('DOUBLE_FA_AUTH')          # → bool

Never reads ``configuration_parameters`` (client/runtime catalog).
Hot-path values are cached briefly in the ``access`` Redis cache
(shared across workers) to avoid a PostgreSQL hit on every request.
"""

from __future__ import annotations

import json
import logging

from django.core.cache import caches

logger = logging.getLogger('app.admin_parameters')

_CASTERS = {
    'STRING': str,
    'INT': int,
    'DECIMAL': float,
    'BOOL': lambda v: v.lower() in ('true', '1', 'yes'),
    'JSON': json.loads,
}

_CACHE_TTL_SECONDS = 30
_CACHE_KEY_PREFIX = 'admin_param:v1:'
_MISS = object()


def _cache():
    return caches['access']


def _cache_key(code: str) -> str:
    return f'{_CACHE_KEY_PREFIX}{code}'


def clear_admin_parameter_cache(code: str | None = None) -> None:
    """Drop cached admin parameter value(s). Best-effort; never raises."""
    try:
        if code:
            _cache().delete(_cache_key(code))
            return
        # No wildcard delete on LocMem; callers pass the code on mutations.
    except Exception as exc:
        logger.warning('Failed to clear admin parameter cache: %s', exc)


def get_admin_parameter(code: str, default=None):
    """Return the cast value of an admin parameter, or *default* if missing.

    Safe from any layer. Never raises; on error returns *default*.
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
        logger.warning('Admin parameter cache read failed for %s: %s', code, exc)

    try:
        from platform.features.configuration.admin_parameters.admin_parameter.models import (
            AdminParameter,
        )
        param = (
            AdminParameter.objects
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
        logger.warning('Failed to read admin parameter %s: %s', code, exc)
        return default
