"""Concurrent-session policy driven by ``MULTI_SESSIONS``.

The parameter is a BOOL. Missing / inactive / false means a company user
may hold at most one live client session: a new login is rejected
(``AUTH_018``) instead of kicking the existing one.

Re-login from the same browser (valid ``refresh_client`` cookie for that
user) is allowed so an expired access token can be replaced.

Cache/Redis failures fail open so a store outage does not freeze login.
"""

from __future__ import annotations

import logging

from core.errors import AppErrorCode, AuthException
from core.parameters import get_parameter

from client.features.security.lifecycle.auth.domain.interfaces import IClientRefreshStore

PARAM = 'MULTI_SESSIONS'

logger = logging.getLogger('app.auth')


def allows_multiple_sessions() -> bool:
    return bool(get_parameter(PARAM, default=False))


class SessionPolicy:
    def __init__(self, tokens: IClientRefreshStore):
        self.tokens = tokens

    def allows_multiple_sessions(self) -> bool:
        return allows_multiple_sessions()

    def ensure_can_open_session(self, user_id, *, current_refresh_raw: str | None = None) -> None:
        if self.allows_multiple_sessions():
            return
        try:
            sessions = self.tokens.list_for_user(user_id)
        except Exception:
            logger.warning('Session listing failed; allowing login', exc_info=True)
            return
        if not sessions:
            return
        if current_refresh_raw and self._refresh_belongs_to_user(current_refresh_raw, user_id):
            return
        raise AuthException(AppErrorCode.AUTH_SESSION_EXISTS)

    def _refresh_belongs_to_user(self, raw_token: str, user_id) -> bool:
        try:
            record = self.tokens.validate(raw_token)
        except Exception:
            logger.warning('Refresh validation failed during session check', exc_info=True)
            return False
        return bool(record) and str(record.get('user_id')) == str(user_id)
