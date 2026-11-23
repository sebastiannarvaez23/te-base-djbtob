"""Concurrent-session policy for admin login (MULTI_SESSIONS).

Admin portal fail-closed: if Redis cannot list sessions while the policy
disallows multiples, a new login is rejected.
"""

from __future__ import annotations

import logging

from core.admin_parameters import get_admin_parameter
from core.auth import refresh_service
from core.errors import AppErrorCode, AuthException

PARAM = 'MULTI_SESSIONS'

logger = logging.getLogger('app.auth')


def allows_multiple_sessions() -> bool:
    return bool(get_admin_parameter(PARAM, default=False))


class AdminSessionPolicy:
    def allows_multiple_sessions(self) -> bool:
        return allows_multiple_sessions()

    def ensure_can_open_session(
        self, user_id, *, current_refresh_raw: str | None = None,
    ) -> None:
        if self.allows_multiple_sessions():
            return
        try:
            sessions = refresh_service.list_for_user(user_id, 'admin')
        except Exception:
            logger.error(
                'Admin session listing failed; rejecting login (fail-closed)',
                exc_info=True,
            )
            raise AuthException(AppErrorCode.AUTH_SESSION_EXISTS)
        if not sessions:
            return
        if current_refresh_raw and self._refresh_belongs_to_user(current_refresh_raw, user_id):
            return
        raise AuthException(AppErrorCode.AUTH_SESSION_EXISTS)

    def _refresh_belongs_to_user(self, raw_token: str, user_id) -> bool:
        try:
            record = refresh_service.validate(raw_token, expected_type='admin')
        except Exception:
            logger.warning('Admin refresh validation failed during session check', exc_info=True)
            return False
        return bool(record) and str(record.get('user_id')) == str(user_id)
