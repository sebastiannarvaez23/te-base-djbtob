"""Consecutive failed-password lockout driven by ``MAX_LOGIN_RETRIES``.

``0`` / inactive / missing disables the policy. Cache failures never block
a legitimate sign-in (fail-open). There is no companion lockout-duration
parameter: the counter lives ``LOCKOUT_TTL_SECONDS`` (15 minutes) from the
first fail, then a full window again once the ceiling is hit.
"""

from __future__ import annotations

import logging

from core.errors import AppErrorCode, AuthException
from core.errors.retry_after import coerce_retry_after
from core.parameters import get_parameter

from client.features.security.lifecycle.auth.domain.interfaces import ILoginRetryStore

PARAM = 'MAX_LOGIN_RETRIES'
_ENABLED_DEFAULT = 4
LOCKOUT_TTL_SECONDS = 15 * 60

logger = logging.getLogger('app.auth')


def max_retries() -> int:
    raw = get_parameter(PARAM, default=0)
    if raw is True:
        return _ENABLED_DEFAULT
    if raw is False or raw is None:
        return 0
    try:
        return max(int(raw), 0)
    except (TypeError, ValueError):
        return 0


class LoginLockout:
    def __init__(self, store: ILoginRetryStore):
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
            logger.warning('Login lockout read failed; allowing attempt', exc_info=True)

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
            logger.warning('Login lockout increment failed; allowing attempt', exc_info=True)

    def clear_failures(self, username: str) -> None:
        try:
            self.store.clear_failures(username)
        except Exception:
            logger.warning('Login lockout clear failed', exc_info=True)

    def _retry_after(self, username: str) -> int | None:
        """Seconds until the lockout window opens, if the store knows.

        TTL read failures must not fail-open the lock: they only omit
        ``retry_after``. Never invent a wait when remaining is unknown.
        """
        try:
            return coerce_retry_after(self.store.ttl_remaining(username))
        except Exception:
            return None
