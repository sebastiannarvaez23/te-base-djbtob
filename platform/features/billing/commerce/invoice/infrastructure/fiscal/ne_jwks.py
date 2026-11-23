"""Neurana public keys (JWKS) for webhook v2 verification, cached in Redis.

An unknown ``kid`` (Neurana rotated) forces one refetch, rate-limited so a
flood of forged signatures cannot hammer Neurana.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('billing.invoice.webhooks')

CACHE_KEY = 'ne:ecosystem:jwks'
REFRESH_LOCK_KEY = 'ne:ecosystem:jwks:refresh'
REFRESH_MIN_INTERVAL_SECONDS = 30
FETCH_TIMEOUT_SECONDS = 3.0


def _fetch() -> dict | None:
    import httpx

    url = (getattr(settings, 'NE_ECOSYSTEM_JWKS_URL', '') or '').strip()
    if not url:
        return None
    try:
        resp = httpx.get(url, timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=False)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001 — fall back to cached keys / v1
        logger.warning('ne_jwks_fetch_failed url=%s error=%s', url, exc)
        return None
    if not isinstance(data, dict) or not isinstance(data.get('keys'), list):
        logger.warning('ne_jwks_invalid_document url=%s', url)
        return None
    return data


def get_ne_keyset(*, force: bool = False):
    from necore.ecosystem.keys import KeySet

    cached = cache.get(CACHE_KEY)
    if cached and not force:
        return KeySet.from_jwks(cached)
    if force and cached and not cache.add(REFRESH_LOCK_KEY, 1, timeout=REFRESH_MIN_INTERVAL_SECONDS):
        return KeySet.from_jwks(cached)
    fresh = _fetch()
    if fresh is None:
        return KeySet.from_jwks(cached) if cached else KeySet()
    cache.set(CACHE_KEY, fresh, timeout=int(getattr(settings, 'NE_JWKS_CACHE_SECONDS', 600)))
    return KeySet.from_jwks(fresh)
