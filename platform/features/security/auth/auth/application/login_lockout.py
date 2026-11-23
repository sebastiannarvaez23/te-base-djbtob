"""Consecutive failed-password lockout for admin login (MAX_LOGIN_RETRIES).

Admin portal fail-closed: if the Redis store is unavailable while the
policy is enabled, login attempts are rejected rather than left open to
brute force.
"""

from __future__ import annotations

import logging

from core.admin_parameters import get_admin_parameter
from core.errors import AppErrorCode, AuthException
from core.errors.retry_after import coerce_retry_after

from platform.features.security.auth.auth.domain.interfaces import IAdminLoginRetryStore

PARAM = 'MAX_LOGIN_RETRIES'
_ENABLED_DEFAULT = 4
LOCKOUT_TTL_SECONDS = 15 * 60

logger = logging.getLogger('app.auth')


def max_retries() -> int:
    raw = get_admin_parameter(PARAM, default=0)
    if raw is True:
        return _ENABLED_DEFAULT
    if raw is False or raw is None:
        return 0
    try:
        return max(int(raw), 0)
    except (TypeError, ValueError):
        return 0


class AdminLoginLockout:
    def __init__(self, store: IAdminLoginRetryStore):
        self.store = store

    def max_retries(self) -> int:
        return max_retries()

    def assert_not_locked(self, username: str) -> None:
        limit = max_retries()
        if limit <= 0:
            return
        try:
            if self.store.get_failures(username) >= limit:
                raise AuthException(
                    AppErrorCode.AUTH_LOGIN_LOCKED,
                    retry_after=self._retry_after(username),
                )
        except AuthException:
            raise
        except Exception:
            logger.error(
                'Admin login lockout read failed; rejecting attempt (fail-closed)',
                exc_info=True,
            )
            raise AuthException(AppErrorCode.AUTH_LOGIN_LOCKED)

    def register_failure(self, username: str) -> None:
        limit = max_retries()
        if limit <= 0:
            return
        try:
            count = self.store.incr_failures(username, LOCKOUT_TTL_SECONDS)
            if count >= limit:
                self.store.refresh_ttl(username, count, LOCKOUT_TTL_SECONDS)
                raise AuthException(
                    AppErrorCode.AUTH_LOGIN_LOCKED,
                    retry_after=self._retry_after(username),
                )
        except AuthException:
            raise
        except Exception:
            logger.error(
                'Admin login lockout increment failed; rejecting attempt (fail-closed)',
                exc_info=True,
            )
            raise AuthException(AppErrorCode.AUTH_LOGIN_LOCKED)

    def clear_failures(self, username: str) -> None:
        try:
            self.store.clear_failures(username)
        except Exception:
            logger.warning('Admin login lockout clear failed', exc_info=True)

    def _retry_after(self, username: str) -> int | None:
        try:
            return coerce_retry_after(self.store.ttl_remaining(username))
        except Exception:
            return None
