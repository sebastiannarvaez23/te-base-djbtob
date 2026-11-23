"""Presupuestos de coste / latencia (Redis hot path, best-effort).

``hourly_budget_usd`` is the rolling hourly window limit.
``route.max_cost_usd``, when set, is treated as an **additional** hourly
window cap for that route (not a per-call ceiling).
"""

from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.conf import settings
from django.core.cache import caches
from django.db import connection

from core.errors import AppErrorCode, ServerException

from .schemas import ModelRouteDecision

logger = logging.getLogger('app.ai')

_CACHE_ALIAS = 'access'
_KEY_PREFIX = 'ai:budget:cost_mc'  # millicents (USD * 100_000)
_WINDOW_TTL = 3600  # 1 hour rolling window
_MILLICENTS = Decimal('100000')


def _cache():
    try:
        return caches[_CACHE_ALIAS]
    except Exception:
        return None


def _tenant() -> str:
    try:
        return getattr(connection, 'schema_name', 'public') or 'public'
    except Exception:
        return 'public'


def _to_millicents(amount: Decimal) -> int:
    return int((amount * _MILLICENTS).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _from_millicents(raw: int) -> Decimal:
    return Decimal(raw) / _MILLICENTS


class BudgetGuard:
    """
    Hard stops económicos antes de invocar un proveedor de pago.

    - ``hourly_budget_usd`` global (settings o tabla de routing)
    - ``route.max_cost_usd`` por capacidad (tope de la misma ventana horaria)
    """

    def __init__(self, *, hourly_budget_usd: Optional[Decimal] = None):
        configured = hourly_budget_usd
        if configured is None:
            raw = getattr(settings, 'AI_HOURLY_BUDGET_USD', None)
            configured = Decimal(str(raw)) if raw not in (None, '') else None
        self.hourly_budget_usd = configured

    def _key(self) -> str:
        return f'{_KEY_PREFIX}:{_tenant()}'

    def spent_usd(self) -> Decimal:
        cache = _cache()
        if cache is None:
            return Decimal('0')
        try:
            raw = cache.get(self._key())
            if raw is None:
                return Decimal('0')
            return _from_millicents(int(raw))
        except Exception as exc:
            logger.debug('budget spent read failed: %s', exc)
            return Decimal('0')

    def assert_allowed(self, route: ModelRouteDecision) -> None:
        """Raise AI_QUOTA_EXCEEDED if the hourly budget would be violated."""
        caps = [c for c in (self.hourly_budget_usd, route.max_cost_usd) if c is not None]
        if not caps:
            return
        limit = min(caps)
        spent = self.spent_usd()
        if spent >= limit:
            raise ServerException(
                AppErrorCode.AI_QUOTA_EXCEEDED,
                override_detail=(
                    f'AI hourly budget exceeded ({spent} >= {limit} USD).'
                ),
            )

    def record_cost(self, amount_usd: float | Decimal) -> None:
        """Atomically add cost using Redis INCR (millicents)."""
        amount = Decimal(str(amount_usd or 0))
        if amount <= 0:
            return
        cache = _cache()
        if cache is None:
            return
        key = self._key()
        delta = _to_millicents(amount)
        if delta <= 0:
            return
        try:
            try:
                cache.incr(key, delta)
            except ValueError:
                # Key missing — seed then incr (best-effort race: may briefly double).
                cache.add(key, 0, timeout=_WINDOW_TTL)
                try:
                    cache.incr(key, delta)
                except ValueError:
                    cache.set(key, delta, timeout=_WINDOW_TTL)
            else:
                # Refresh TTL on successful incr so the window keeps rolling.
                try:
                    cache.touch(key, _WINDOW_TTL)
                except Exception:
                    pass
        except Exception as exc:
            logger.debug('budget cost write failed: %s', exc)
