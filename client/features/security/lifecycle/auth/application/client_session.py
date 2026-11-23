"""Client session open / close use cases."""

from __future__ import annotations

from core.auth.refresh_service import refresh_ttl_seconds

from client.features.security.lifecycle.auth.application.session_policy import SessionPolicy
from client.features.security.lifecycle.auth.application.use_cases import BuildSessionUseCase
from client.features.security.lifecycle.auth.domain.interfaces import (
    IAuthRepository,
    IClientRefreshStore,
)
from client.features.security.lifecycle.auth.domain.schemas import AuthenticatedClient, IssuedClientSession
from core.access.billing_recovery import LoginAccessResult
from core.trace import trace_layer


class IssueClientSessionUseCase:
    """Assert MULTI_SESSIONS, stamp last_login, mint a refresh session."""

    def __init__(
        self,
        *,
        build_session: BuildSessionUseCase,
        auth_repository: IAuthRepository,
        tokens: IClientRefreshStore,
        policy: SessionPolicy,
    ):
        self.build_session = build_session
        self.auth_repository = auth_repository
        self.tokens = tokens
        self.policy = policy

    @trace_layer('application')
    def execute(
        self,
        user: object,
        *,
        access: LoginAccessResult | None = None,
        current_refresh_raw: str | None,
        schema_name: str,
        ip: str,
        user_agent: str,
        remember_me: bool = False,
    ) -> IssuedClientSession:
        remembered = bool(remember_me)
        self.policy.ensure_can_open_session(
            user.pk,
            current_refresh_raw=current_refresh_raw,
        )
        self.auth_repository.touch_last_login(user)
        session = self.build_session.execute(user, access=access)

        if self.policy.allows_multiple_sessions():
            if current_refresh_raw:
                self.tokens.revoke(current_refresh_raw)
        else:
            self.tokens.revoke_all_for_user(user.pk)

        raw_refresh = self.tokens.generate_raw_token()
        _, session_id = self.tokens.store(
            raw_token=raw_refresh,
            user_id=user.pk,
            schema_name=schema_name,
            ip_address=ip or '',
            user_agent=user_agent or '',
            ttl_seconds=refresh_ttl_seconds(remember_me=remembered),
            remember_me=remembered,
        )
        return IssuedClientSession(
            session=session,
            refresh_token=raw_refresh,
            session_id=session_id,
            remember_me=remembered,
        )


class LogoutClientSessionUseCase:
    """Revoke this browser's token (multi on) or every client session (multi off)."""

    def __init__(self, *, tokens: IClientRefreshStore, policy: SessionPolicy):
        self.tokens = tokens
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
                self.tokens.revoke(current_refresh_raw)
            elif access_user_id and access_session_id:
                self.tokens.revoke_session(access_user_id, access_session_id)
            return

        user_id = access_user_id
        if user_id is None and current_refresh_raw:
            record = self.tokens.validate(current_refresh_raw)
            if record:
                user_id = record.get('user_id')
        if user_id:
            self.tokens.revoke_all_for_user(user_id)
