"""Backward-compatible re-export — implementation lives in ``core.auth``."""

from __future__ import annotations

from core.auth import login_retry_store as base
from core.auth.login_retry_store import (  # noqa: F401
    clear_failures,
    get_failures,
    incr_failures,
    refresh_ttl,
    schema_name,
    ttl_remaining,
)
from client.features.security.lifecycle.auth.domain.interfaces import ILoginRetryStore


class CacheLoginRetryStore(ILoginRetryStore):
    """ILoginRetryStore adapter over the ``auth`` cache."""

    def incr_failures(self, username: str, ttl_seconds: int) -> int:
        return base.incr_failures(username, ttl_seconds)

    def get_failures(self, username: str) -> int:
        return base.get_failures(username)

    def refresh_ttl(self, username: str, count: int, ttl_seconds: int) -> None:
        base.refresh_ttl(username, count, ttl_seconds)

    def clear_failures(self, username: str) -> None:
        base.clear_failures(username)

    def ttl_remaining(self, username: str) -> int | None:
        return base.ttl_remaining(username)
