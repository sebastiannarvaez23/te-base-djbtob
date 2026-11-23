"""Issue / close admin sessions with MULTI_SESSIONS enforcement."""

from __future__ import annotations

from core.auth import refresh_service
from core.auth.jwt_service import create_access_token
from core.trace import trace_layer
from platform.features.security.auth.auth.application.password_policy import start_password_clock
from platform.features.security.auth.auth.application.session_policy import AdminSessionPolicy
from platform.features.security.auth.auth.domain.interfaces import IAdminAuthRepository
from platform.features.security.auth.auth.domain.schemas import IssuedAdminSession


class IssueAdminSessionUseCase:
    """Assert MULTI_SESSIONS, stamp last_login, mint access + refresh tokens."""

    def __init__(
        self,
        *,
        auth_repository: IAdminAuthRepository,
        policy: AdminSessionPolicy,
    ):
        self.auth_repository = auth_repository
        self.policy = policy

    @trace_layer('application')
    def execute(
        self,
        user,
        *,
        current_refresh_raw: str | None,
        ip: str = '',
        user_agent: str = '',
        last_activity_at: str | None = None,
    ) -> IssuedAdminSession:
        self.policy.ensure_can_open_session(
            user.pk,
            current_refresh_raw=current_refresh_raw,
        )
        self.auth_repository.touch_last_login(user)
        start_password_clock(user)

        if self.policy.allows_multiple_sessions():
            if current_refresh_raw:
                refresh_service.revoke(current_refresh_raw, user_type='admin')
        else:
            # Pre-clear; post-store revoke_others closes the concurrent race.
            refresh_service.revoke_all_for_user(user.pk, user_type='admin')

        raw_refresh = refresh_service.generate_raw_token()
        _, token_id = refresh_service.store(
            raw_token=raw_refresh,
            user_id=user.pk,
            user_type='admin',
            schema_name='public',
            ip_address=ip or '',
            user_agent=user_agent or '',
            last_activity_at=last_activity_at,
        )
        if not self.policy.allows_multiple_sessions():
            refresh_service.revoke_others_for_user(
                user.pk, 'admin', keep_token_id=token_id,
            )

        access_token = create_access_token(
            user_id=user.pk,
            user_type='admin',
            schema_name='public',
            session_id=token_id,
            username=getattr(user, 'username', '') or '',
        )
        return IssuedAdminSession(
            user=user,
            access_token=access_token,
            refresh_token=raw_refresh,
            session_id=token_id,
        )


class LogoutAdminSessionUseCase:
    """Revoke this browser's token (multi on) or every admin session (multi off)."""

    def __init__(self, *, policy: AdminSessionPolicy):
        self.policy = policy

    @trace_layer('application')
    def execute(
        self,
        *,
        current_refresh_raw: str | None,
        access_user_id=None,
        access_session_id: str | None = None,
    ) -> None:
        if self.policy.allows_multiple_sessions():
            if current_refresh_raw:
                refresh_service.revoke(current_refresh_raw, user_type='admin')
            elif access_user_id and access_session_id:
                refresh_service.revoke_session('admin', access_user_id, access_session_id)
            return

        user_id = access_user_id
        if user_id is None and current_refresh_raw:
            record = refresh_service.validate(current_refresh_raw, expected_type='admin')
            if record:
                user_id = record.get('user_id')
        if user_id:
            refresh_service.revoke_all_for_user(user_id, user_type='admin')
