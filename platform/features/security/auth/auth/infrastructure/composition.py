from platform.features.security.auth.auth.application.admin_session import (
    IssueAdminSessionUseCase,
    LogoutAdminSessionUseCase,
)
from platform.features.security.auth.auth.application.login_lockout import AdminLoginLockout
from platform.features.security.auth.auth.application.session_policy import AdminSessionPolicy
from platform.features.security.auth.auth.application.two_factor import (
    FindAdminTrustedDeviceUseCase,
    GetActiveAdminTwoFactorChallengeUseCase,
    IssueAdminTwoFactorChallengeUseCase,
    PeekAdminTwoFactorChallengeUseCase,
    RegisterAdminTrustedDeviceUseCase,
    RotateAdminTwoFactorChallengeUseCase,
    TouchAdminTrustedDeviceUseCase,
    VerifyAdminTwoFactorChallengeUseCase,
)
from platform.features.security.auth.auth.infrastructure.login_retry_store import (
    CacheAdminLoginRetryStore,
)
from platform.features.security.auth.auth.infrastructure.repositories import (
    DjangoAdminAuthRepository,
    DjangoAdminTrustedDeviceRepository,
    DjangoAdminUserLookup,
)


def admin_login_lockout() -> AdminLoginLockout:
    return AdminLoginLockout(CacheAdminLoginRetryStore())


def admin_session_policy() -> AdminSessionPolicy:
    return AdminSessionPolicy()


def issue_admin_session() -> IssueAdminSessionUseCase:
    return IssueAdminSessionUseCase(
        auth_repository=DjangoAdminAuthRepository(),
        policy=admin_session_policy(),
    )


def logout_admin_session() -> LogoutAdminSessionUseCase:
    return LogoutAdminSessionUseCase(policy=admin_session_policy())


def _devices() -> DjangoAdminTrustedDeviceRepository:
    return DjangoAdminTrustedDeviceRepository()


def _users() -> DjangoAdminUserLookup:
    return DjangoAdminUserLookup()


def find_admin_trusted_device() -> FindAdminTrustedDeviceUseCase:
    return FindAdminTrustedDeviceUseCase(_devices())


def touch_admin_trusted_device() -> TouchAdminTrustedDeviceUseCase:
    return TouchAdminTrustedDeviceUseCase(_devices())


def register_admin_trusted_device() -> RegisterAdminTrustedDeviceUseCase:
    return RegisterAdminTrustedDeviceUseCase(_devices())


def issue_admin_two_factor_challenge() -> IssueAdminTwoFactorChallengeUseCase:
    return IssueAdminTwoFactorChallengeUseCase()


def get_active_admin_two_factor_challenge() -> GetActiveAdminTwoFactorChallengeUseCase:
    return GetActiveAdminTwoFactorChallengeUseCase()


def peek_admin_two_factor_challenge() -> PeekAdminTwoFactorChallengeUseCase:
    return PeekAdminTwoFactorChallengeUseCase(_users())


def rotate_admin_two_factor_challenge() -> RotateAdminTwoFactorChallengeUseCase:
    return RotateAdminTwoFactorChallengeUseCase(_users())


def verify_admin_two_factor_challenge() -> VerifyAdminTwoFactorChallengeUseCase:
    return VerifyAdminTwoFactorChallengeUseCase(_users())
