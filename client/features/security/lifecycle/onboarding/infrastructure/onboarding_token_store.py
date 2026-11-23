"""Opaque onboarding-token → registration_id mappings, backed by Redis.

Two separate stores share the same backing cache but use different key
namespaces:

  * ``RedisOnboardingTokenStore`` — short-lived (hours) session handle
    that lives in the onboarding cookie.
  * ``RedisOnboardingResumeTokenStore`` — long-lived (days) magic-link
    token sent over email so the user can resume their registration.

Keeping them separate prevents a leaked email link from acting as a
session cookie or vice-versa.
"""

import secrets
from typing import Optional
from uuid import UUID

from django.core.cache import caches

from ..domain.interfaces import IOnboardingResumeTokenStore, IOnboardingTokenStore


def _cache():
    return caches['auth']


class _BaseRedisTokenStore:
    _PREFIX = ''

    @classmethod
    def _key(cls, token: str) -> str:
        return f'{cls._PREFIX}{token}'

    def issue(self, registration_id: UUID, ttl_seconds: int) -> str:
        token = secrets.token_urlsafe(32)
        _cache().set(self._key(token), str(registration_id), timeout=ttl_seconds)
        return token

    def resolve(self, token: str) -> Optional[UUID]:
        if not token:
            return None
        raw = _cache().get(self._key(token))
        if raw is None:
            return None
        try:
            return UUID(raw)
        except (TypeError, ValueError):
            return None

    def revoke(self, token: str) -> None:
        if token:
            _cache().delete(self._key(token))


class RedisOnboardingTokenStore(_BaseRedisTokenStore, IOnboardingTokenStore):
    _PREFIX = 'onb:'


class RedisOnboardingResumeTokenStore(_BaseRedisTokenStore, IOnboardingResumeTokenStore):
    _PREFIX = 'onb:resume:'
