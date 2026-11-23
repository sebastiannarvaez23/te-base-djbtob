from client.features.security.lifecycle.auth.application.login_lockout import LoginLockout
from client.features.security.lifecycle.auth.domain.interfaces import IAuthRepository, ISessionRepository
from client.features.security.lifecycle.auth.domain.schemas import (
    AuthenticatedClient,
    CompanyInfoSchema,
    SessionSchema,
    UserInfoSchema,
)
from core.access.billing_recovery import LoginAccessResult, resolve_login_access_for_user
from core.auth.inactivity import inactivity_minutes
from client.features.security.identity.identity.domain.profile_picture import (
    resolve_profile_picture_url,
    user_picture_object_key,
)
from core.errors import AppErrorCode, AuthException, SubscriptionException
from platform.features.compliance.policy.policy.application.pending_for_user import (
    pending_policies_for_user,
)
from platform.features.company.tenant.company.domain.location import company_location_labels
from core.trace import trace_layer


class LoginUserUseCase:
    def __init__(self, repository: IAuthRepository, lockout: LoginLockout | None = None):
        self.repository = repository
        self.lockout = lockout

    @trace_layer('application')
    def execute(self, username: str, password: str) -> AuthenticatedClient:
        """Authenticate user. Raises AuthException on failure."""
        if self.lockout is not None:
            self.lockout.assert_not_locked(username)
        try:
            auth = self.repository.authenticate(username, password)
        except AuthException as exc:
            if self.lockout is not None:
                if exc.code == AppErrorCode.AUTH_INVALID_CREDENTIALS:
                    self.lockout.register_failure(username)
                else:
                    self.lockout.clear_failures(username)
            raise
        except SubscriptionException:
            if self.lockout is not None:
                self.lockout.clear_failures(username)
            raise
        if self.lockout is not None:
            self.lockout.clear_failures(username)
        return auth


class BuildSessionUseCase:
    def __init__(self, session_repository: ISessionRepository):
        self.session_repository = session_repository

    @trace_layer('application')
    def execute(
        self,
        user: object,
        *,
        access: LoginAccessResult | None = None,
    ) -> SessionSchema:
        if access is None:
            access = resolve_login_access_for_user(user)
        company = user.company
        domain = self.session_repository.get_company_domain(company)
        preferences = self.session_repository.get_or_create_preferences(user)
        subscription = self.session_repository.get_active_subscription(company)

        if access.is_billing_recovery:
            menu, features = self.session_repository.build_billing_recovery_menu(user.rol)
        else:
            subscription_id = subscription.id if subscription else None
            menu, features = self.session_repository.build_menu(
                user.rol, subscription_id, str(company.id),
            )

        requires_policy_acceptance = False
        policy_country = None
        if not access.is_billing_recovery:
            # Fail-closed: a broken policy catalog must not silently bypass the gate.
            pending, policy_country = pending_policies_for_user(user)
            requires_policy_acceptance = bool(pending)

        country_name, state_name, city_name = company_location_labels(company)

        return SessionSchema(
            user=UserInfoSchema(
                id=str(user.id),
                username=user.username,
                first_name=(getattr(user, 'first_name', None) or '').strip(),
                second_name=(getattr(user, 'second_name', None) or '').strip(),
                rol=user.rol.name if user.rol else None,
                picture=resolve_profile_picture_url(user_picture_object_key(user)),
                preferences=preferences,
            ),
            company=CompanyInfoSchema(
                id=str(company.id),
                name=company.name,
                nit=company.nit,
                address=company.address,
                country=country_name,
                state=state_name,
                city=city_name,
                domain=domain,
                subscription=subscription,
            ),
            menu=menu,
            features=features,
            access_mode=access.mode,
            subscription_status=access.subscription_status or (
                subscription.status if subscription else None
            ),
            requires_policy_acceptance=requires_policy_acceptance,
            policy_country=policy_country,
            inactivity_minutes=inactivity_minutes(),
        )
