"""Admin login failure counter — Redis keys scoped to schema ``admin``."""

from __future__ import annotations

from core.auth import login_retry_store as base
from platform.features.security.auth.auth.domain.interfaces import IAdminLoginRetryStore

_ADMIN_SCHEMA = 'admin'


class CacheAdminLoginRetryStore(IAdminLoginRetryStore):

    def incr_failures(self, username: str, ttl_seconds: int) -> int:
        return base.incr_failures(username, ttl_seconds, schema=_ADMIN_SCHEMA)

    def get_failures(self, username: str) -> int:
        return base.get_failures(username, schema=_ADMIN_SCHEMA)

    def refresh_ttl(self, username: str, count: int, ttl_seconds: int) -> None:
        base.refresh_ttl(username, count, ttl_seconds, schema=_ADMIN_SCHEMA)

    def clear_failures(self, username: str) -> None:
        base.clear_failures(username, schema=_ADMIN_SCHEMA)

    def ttl_remaining(self, username: str) -> int | None:
        return base.ttl_remaining(username, schema=_ADMIN_SCHEMA)
