"""Cache-backed throttle for onboarding resume-link re-sends.

``cache.add`` over the ``auth`` Redis cache gives SET NX semantics — the
return value tells us whether *we* set the key, atomically blocking any
other caller within the same window.

The window is configured via the ``ONB_RESUME_WND_S`` runtime parameter
(fallback: 60 seconds). Keyed by lowercased email so a user pasting the
same address with mixed casing is throttled the same way.
"""
from __future__ import annotations

from django.core.cache import caches

from core.errors.retry_after import cache_retry_after
from core.parameters import get_parameter

from client.features.security.lifecycle.onboarding.domain.interfaces import IResumeLinkThrottle


def _cache():
    return caches['auth']


def _window_seconds() -> int:
    return int(get_parameter('ONB_RESUME_WND_S', default=60))


def _slot_key(email: str) -> str:
    return f'onboarding_resume_throttle:{email.lower()}'


class CacheResumeLinkThrottle(IResumeLinkThrottle):
    """IResumeLinkThrottle adapter over the ``auth`` cache."""

    def try_acquire(self, email: str) -> bool:
        return bool(_cache().add(_slot_key(email), '1', timeout=_window_seconds()))

    def retry_after(self, email: str) -> int | None:
        return cache_retry_after(_cache(), _slot_key(email))
