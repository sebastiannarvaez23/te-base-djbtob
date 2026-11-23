"""
core/cache/decorators.py
────────────────────────
Decorador genérico para cachear el resultado de use cases en Redis.

Uso:
    @use_case_cache(prefix="parameters")
    def execute(self) -> List[ParameterSchema]:
        ...                          → clave: "parameters"

    @use_case_cache(prefix="parameters")
    def execute(self, id: uuid.UUID) -> ParameterSchema:
        ...                          → clave: "parameters:<id>"
"""

from __future__ import annotations

import functools
import logging

from django.core.cache import caches

logger = logging.getLogger('app.api')

TTL = 300  # 5 minutos — valor único para todo el sistema de caché


def _cache():
    return caches['access']


def _build_key(prefix: str, args, kwargs) -> str:
    """Construye la clave de caché de forma determinista.

    Los posicionales van por valor; los kwargs van como ``nombre=valor``
    ordenados por nombre. Así ``fn(1, 2)`` y ``fn(a=1, b=2)`` no colisionan
    entre sí ni dependen del orden en que se pasen los kwargs (un dict con
    otro orden de inserción produciría la MISMA clave).
    """
    parts = [str(a) for a in args]
    parts += [f'{k}={kwargs[k]}' for k in sorted(kwargs)]
    if not parts:
        return prefix
    return f'{prefix}:{":".join(parts)}'


def use_case_cache(prefix: str):
    """
    Cachea el resultado de un método en Redis (backend 'access').

    Parámetros
    ----------
    prefix : str
        Prefijo de la clave. Si el método recibe argumentos (aparte de self),
        se concatenan al prefijo (posicionales por valor, kwargs como
        ``nombre=valor`` ordenados).

    ⚠️ Multi-tenant: la clave NO incluye el schema del tenant. Es seguro solo
    para use cases sobre datos del schema público (p. ej. ``parameters``). NO
    lo apliques a datos particionados por tenant sin añadir el schema al
    prefijo, o se filtrarían resultados entre empresas.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            cache_key = _build_key(prefix, args, kwargs)

            try:
                cached = _cache().get(cache_key)
                if cached is not None:
                    logger.debug('Cache HIT: %s', cache_key)
                    return cached
            except Exception:
                logger.warning('Cache read failed: %s', cache_key, exc_info=True)

            result = fn(self, *args, **kwargs)

            try:
                _cache().set(cache_key, result, timeout=TTL)
                logger.debug('Cache SET: %s', cache_key)
            except Exception:
                logger.warning('Cache write failed: %s', cache_key, exc_info=True)

            return result
        return wrapper
    return decorator
