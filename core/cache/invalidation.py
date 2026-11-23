"""
core/cache/invalidation.py
──────────────────────────
Invalidación de caché en Redis.

Uso:
    invalidate_cache("parameters:*")      # borra todo el grupo
    invalidate_cache("parameters:all")    # borra una clave exacta
    bump_versions(["a:v", "b:v"], 86400)  # nueva versión por clave, un viaje, tras COMMIT
"""

from __future__ import annotations

import logging
import uuid
from typing import Iterable

from django.core.cache import caches
from django.db import transaction

logger = logging.getLogger('app.api')


def _cache():
    return caches['access']


def new_version() -> str:
    """Token aleatorio: una versión recreada tras una expulsión nunca coincide con otra vieja."""
    return uuid.uuid4().hex


def invalidate_cache(pattern: str) -> None:
    """
    Elimina claves de Redis que coincidan con el patrón.

    Si el patrón contiene '*', usa delete_pattern (django-redis).
    De lo contrario, elimina la clave exacta.
    """
    try:
        if '*' in pattern:
            _cache().delete_pattern(pattern)
        else:
            _cache().delete(pattern)
        logger.debug('Cache INVALIDATED: %s', pattern)
    except Exception:
        logger.warning('Cache invalidation failed: %s', pattern, exc_info=True)


def bump_versions(version_keys: Iterable[str], timeout: int) -> None:
    """
    Asigna una versión nueva a cada clave en un solo viaje (``set_many``).

    Los valores cacheados con la versión anterior quedan descartados aunque una
    lectura concurrente los escriba después. Dentro de una transacción espera
    al COMMIT, para que la versión nueva solo exista con los datos confirmados.
    """
    pending = list(version_keys)
    if not pending:
        return

    def bump() -> None:
        try:
            _cache().set_many({key: new_version() for key in pending}, timeout=timeout)
            logger.debug('Cache VERSIONS BUMPED: %d keys', len(pending))
        except Exception:
            logger.warning('Cache version bump failed: %d keys', len(pending), exc_info=True)

    transaction.on_commit(bump)
