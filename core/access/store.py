"""
core/access/store.py
────────────────────
Almacén de contadores de uso sobre Redis (vía django.core.cache).

Todas las operaciones son O(1) y atómicas. No se realiza ninguna
consulta a PostgreSQL en el hot path.

Usa el backend de caché 'access' (Redis) en lugar del 'default'
para no interferir con el throttling de DRF ni otras funciones
de Django que usan el caché por defecto.

Convención de claves
────────────────────
    usage:{company_id}:{feature_key}:daily:{YYYY-MM-DD}     → int  (TTL 48h)
    usage:{company_id}:{feature_key}:lifetime               → int  (sin TTL)
    usage:{company_id}:{feature_key}:window:{Nh}:{slot}     → int  (TTL resto de ventana + 1h)


Durabilidad del contador lifetime
─────────────────────────────────
El contador lifetime no tiene TTL, pero Redis NO es la fuente de verdad:
un reinicio sin persistencia, un ``FLUSHDB`` o una evicción por ``maxmemory``
pueden perderlo. Para no sub/sobre-contar tras esa pérdida, ``get_lifetime``
se auto-repara: si la clave no existe y la feature tiene un counter real
registrado (``core.access.registry``), re-siembra el valor desde PostgreSQL.
El warmup solo siembra al arrancar; esto cubre las pérdidas en runtime.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timezone
from typing import Optional

from django.core.cache import caches

from core.access.window_hours import coerce_window_hours

logger = logging.getLogger('app.api')

_DAILY_TTL = 48 * 3600  # 48 horas — se auto-elimina sin cron


def _cache():
    """Retorna el backend de caché 'access' (Redis)."""
    return caches['access']


class UsageStore:
    """Contadores de uso atómicos sobre Redis."""

    # ── Claves ────────────────────────────────────────────────────────

    @staticmethod
    def _daily_key(company_id: str, feature_key: str) -> str:
        return f'usage:{company_id}:{feature_key}:daily:{date.today().isoformat()}'

    @staticmethod
    def _lifetime_key(company_id: str, feature_key: str) -> str:
        return f'usage:{company_id}:{feature_key}:lifetime'

    @staticmethod
    def window_slot(window_hours: int, *, now: float | None = None) -> int:
        """Índice de la ventana fija alineada a epoch UTC.

        Con window_hours=3, un día de 24 h tiene exactamente 8 ventanas
        (00:00–03:00, 03:00–06:00, …). El contador se recarga al cambiar de slot.
        """
        hours = coerce_window_hours(window_hours)
        period = hours * 3600
        ts = int(now if now is not None else time.time())
        return ts // period

    @staticmethod
    def window_reset_at(window_hours: int, *, now: float | None = None) -> datetime:
        """Inicio UTC de la siguiente ventana fija (cuando se recarga el cupo)."""
        hours = coerce_window_hours(window_hours)
        period = hours * 3600
        ts = int(now if now is not None else time.time())
        end = (ts // period + 1) * period
        return datetime.fromtimestamp(end, tz=timezone.utc)

    @staticmethod
    def daily_reset_at(*, now: float | None = None) -> datetime:
        """Siguiente medianoche UTC (cuando se recarga el tope diario)."""
        ts = int(now if now is not None else time.time())
        end = (ts // 86400 + 1) * 86400
        return datetime.fromtimestamp(end, tz=timezone.utc)

    @staticmethod
    def _window_key(company_id: str, feature_key: str, window_hours: int, *, now: float | None = None) -> str:
        hours = coerce_window_hours(window_hours)
        slot = UsageStore.window_slot(hours, now=now)
        return f'usage:{company_id}:{feature_key}:window:{hours}h:{slot}'

    @staticmethod
    def _window_ttl(window_hours: int, *, now: float | None = None) -> int:
        hours = coerce_window_hours(window_hours)
        period = hours * 3600
        ts = int(now if now is not None else time.time())
        slot = ts // period
        remaining = (slot + 1) * period - ts
        return max(remaining, 1) + 3600

    @staticmethod
    def get_window(company_id: str, feature_key: str, window_hours: int) -> int:
        """Retorna el consumo de la ventana actual (0 si no existe la clave)."""
        return _cache().get(UsageStore._window_key(company_id, feature_key, window_hours), 0)

    @staticmethod
    def increment_window(company_id: str, feature_key: str, window_hours: int) -> int:
        """Incrementa el contador de la ventana actual en 1 y retorna el nuevo valor."""
        key = UsageStore._window_key(company_id, feature_key, window_hours)
        ttl = UsageStore._window_ttl(window_hours)
        try:
            value = _cache().incr(key)
            return value if value is not None else 0
        except ValueError:
            _cache().set(key, 1, timeout=ttl)
            return 1

    # ── Lectura ───────────────────────────────────────────────────────

    @staticmethod
    def get_daily(company_id: str, feature_key: str) -> int:
        """Retorna el consumo diario actual (0 si no existe la clave)."""
        return _cache().get(UsageStore._daily_key(company_id, feature_key), 0)

    @staticmethod
    def get_lifetime(company_id: str, feature_key: str) -> int:
        """Retorna el consumo acumulado por suscripción.

        Si la clave no existe (miss real: nunca sembrada, evicción, FLUSHDB o
        reinicio de Redis) intenta auto-repararse re-sembrando el conteo real
        desde la BD cuando la feature tiene un counter registrado. Si no hay
        counter registrado, retorna 0 (comportamiento previo).
        """
        key = UsageStore._lifetime_key(company_id, feature_key)
        value = _cache().get(key)
        if value is not None:
            return value
        return UsageStore._reseed_lifetime_from_db(company_id, feature_key)

    @staticmethod
    def _reseed_lifetime_from_db(company_id: str, feature_key: str) -> int:
        """Re-siembra el contador lifetime desde PostgreSQL en un miss.

        Import perezoso del registry para evitar ciclos de importación y para
        no pagar el costo salvo en el (raro) camino de miss.
        """
        from core.access.registry import usage_registry

        real_count = usage_registry.get_count(feature_key, company_id)
        if real_count is None:
            # Feature sin counter registrado: no hay forma de reconstruir.
            return 0
        UsageStore.set_lifetime(company_id, feature_key, real_count)
        logger.info(
            'LIFETIME_COUNTER_RESEEDED company=%s feature=%s value=%s',
            company_id, feature_key, real_count,
        )
        return real_count

    # ── Incremento atómico ────────────────────────────────────────────

    @staticmethod
    def increment_daily(company_id: str, feature_key: str) -> int:
        """Incrementa el contador diario en 1 y retorna el nuevo valor."""
        key = UsageStore._daily_key(company_id, feature_key)
        try:
            # Con IGNORE_EXCEPTIONS=True, un fallo de Redis NO lanza: incr
            # retorna None. Normalizamos a 0 para respetar el contrato -> int
            # (degradación grácil; el llamador ignora el valor en ese caso).
            value = _cache().incr(key)
            return value if value is not None else 0
        except ValueError:
            # La clave no existe aún; crearla con valor 1
            _cache().set(key, 1, timeout=_DAILY_TTL)
            return 1

    @staticmethod
    def increment_lifetime(company_id: str, feature_key: str) -> int:
        """Incrementa el contador lifetime en 1 y retorna el nuevo valor."""
        key = UsageStore._lifetime_key(company_id, feature_key)
        try:
            value = _cache().incr(key)
            return value if value is not None else 0
        except ValueError:
            _cache().set(key, 1, timeout=None)
            return 1

    # ── Escritura directa (warmup / sincronización) ──────────────────

    @staticmethod
    def set_lifetime(company_id: str, feature_key: str, value: int) -> None:
        """Establece el contador lifetime a un valor específico (sin TTL).

        Usado durante el warmup para sembrar el conteo real desde la BD.
        """
        _cache().set(UsageStore._lifetime_key(company_id, feature_key), value, timeout=None)

    # ── Decremento atómico ─────────────────────────────────────────────

    @staticmethod
    def decrement_lifetime(company_id: str, feature_key: str) -> int:
        """Decrementa el contador lifetime en 1 (mínimo 0) y retorna el nuevo valor.

        Usado cuando se elimina un recurso (ej: borrar un método de pago).
        """
        key = UsageStore._lifetime_key(company_id, feature_key)
        try:
            new_val = _cache().decr(key)
            if new_val is None:
                # Redis inalcanzable (IGNORE_EXCEPTIONS); nada que decrementar.
                return 0
            if new_val < 0:
                _cache().set(key, 0, timeout=None)
                return 0
            return new_val
        except ValueError:
            # La clave no existe; nada que decrementar
            return 0

    # ── Reset (admin / cambio de plan) ────────────────────────────────

    @staticmethod
    def reset_lifetime(company_id: str, feature_key: str) -> None:
        """Elimina el contador lifetime (ej: al cambiar de plan)."""
        _cache().delete(UsageStore._lifetime_key(company_id, feature_key))

    @staticmethod
    def reset_all_company(company_id: str) -> None:
        """Elimina TODOS los contadores de una empresa.

        Útil al cambiar de plan de suscripción. Usa key pattern delete
        si el backend lo soporta (django-redis sí); de lo contrario
        es un no-op silencioso.
        """
        try:
            _cache().delete_pattern(f'usage:{company_id}:*')
        except AttributeError:
            # Backend sin soporte de patterns (ej: LocMemCache en tests)
            logger.warning('Cache backend does not support delete_pattern')
