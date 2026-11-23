"""Composition root for client auth — wires ports to adapters."""

from client.features.security.lifecycle.auth.application.client_session import (
    IssueClientSessionUseCase,
    LogoutClientSessionUseCase,
)
from client.features.security.lifecycle.auth.application.login_lockout import LoginLockout
from client.features.security.lifecycle.auth.application.session_policy import SessionPolicy
from client.features.security.lifecycle.auth.application.use_cases import (
    BuildSessionUseCase,
    LoginUserUseCase,
)
from client.features.security.lifecycle.auth.infrastructure.login_retry_store import CacheLoginRetryStore
from client.features.security.lifecycle.auth.infrastructure.refresh_token_store import RedisClientRefreshStore
from client.features.security.lifecycle.auth.infrastructure.repositories import (
    DjangoAuthRepository,
    DjangoSessionRepository,
)


def login_user_use_case() -> LoginUserUseCase:
    return LoginUserUseCase(
        DjangoAuthRepository(),
        LoginLockout(CacheLoginRetryStore()),
    )


def session_policy() -> SessionPolicy:
    return SessionPolicy(RedisClientRefreshStore())


def issue_client_session_use_case() -> IssueClientSessionUseCase:
    tokens = RedisClientRefreshStore()
    return IssueClientSessionUseCase(
        build_session=BuildSessionUseCase(DjangoSessionRepository()),
        auth_repository=DjangoAuthRepository(),
        tokens=tokens,
        policy=SessionPolicy(tokens),
    )


def logout_client_session_use_case() -> LogoutClientSessionUseCase:
    tokens = RedisClientRefreshStore()
    return LogoutClientSessionUseCase(
        tokens=tokens,
        policy=SessionPolicy(tokens),
    )
