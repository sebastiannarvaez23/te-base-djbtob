from typing import Optional, Tuple

from django.contrib.auth import get_user_model
from django.utils import timezone

from client.features.security.lifecycle.auth.domain.interfaces import IAuthRepository, ISessionRepository
from client.features.security.lifecycle.auth.domain.schemas import (
    AuthenticatedClient,
    MenuItemSchema,
    PreferencesSchema,
    SubscriptionInfoSchema,
)
from core.access.entitlement import acquisition_grants_access
from core.access.billing_recovery import (
    BILLING_RECOVERY_FEATURES,
    BILLING_RECOVERY_MODULE_CODE,
    fetch_latest_acquisition,
    resolve_login_access,
)
from core.errors import AppErrorCode, AuthException, EmailNotVerifiedException, SubscriptionException
from core.parameters import get_parameter
from platform.features.company.tenant.company.domain.lifecycle import CLOSED_LIFECYCLES


def touch_last_login(user) -> None:
    """Record a completed sign-in. Not called on credential checks that do not issue a session."""
    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])


class DjangoAuthRepository(IAuthRepository):

    def authenticate(self, username: str, password: str) -> AuthenticatedClient:
        User = get_user_model()
        try:
            user = User.objects.select_related(
                'rol',
                'company',
                'company__geo_city__department__country',
            ).get(username=username)
        except User.DoesNotExist:
            raise AuthException(AppErrorCode.AUTH_INVALID_CREDENTIALS)

        if not user.check_password(password):
            raise AuthException(AppErrorCode.AUTH_INVALID_CREDENTIALS)

        lifecycle = getattr(user.company, 'lifecycle', None) or 'ACTIVE'
        if lifecycle in CLOSED_LIFECYCLES:
            raise AuthException(AppErrorCode.AUTH_COMPANY_CLOSED)

        if not user.is_active:
            raise AuthException(AppErrorCode.AUTH_ACCOUNT_INACTIVE)

        # Email confirmation gate. Raised AFTER credentials are validated so
        # that an attacker can't use the response code to enumerate which
        # accounts exist but are unverified.
        if bool(get_parameter('REG_EMAIL_CONFIRM', default=False)):
            if user.email_verified_at is None:
                raise EmailNotVerifiedException(
                    AppErrorCode.AUTH_EMAIL_NOT_VERIFIED,
                    context={'user_id': str(user.pk)},
                )

        if user.rol and not user.rol.is_active:
            raise AuthException(AppErrorCode.AUTH_ROLE_DISABLED, context={'role': user.rol.name})

        latest_sub = fetch_latest_acquisition(user.company)
        access = resolve_login_access(user, latest_sub)
        if access.is_billing_recovery:
            return AuthenticatedClient(user=user, access=access)

        # Cancelada con end_date futuro sigue vigente. Suspendida o vencida no.
        if not acquisition_grants_access(latest_sub):
            raise AuthException(AppErrorCode.AUTH_COMPANY_SUSPENDED)

        # Plan de catálogo desactivado: denegar en el login (no emitir sesión).
        plan = getattr(latest_sub, 'subscription', None)
        if plan is not None and not bool(getattr(plan, 'is_active', True)):
            raise SubscriptionException(AppErrorCode.SUB_NO_ACTIVE)

        return AuthenticatedClient(user=user, access=access)

    def touch_last_login(self, user: object) -> None:
        touch_last_login(user)


class DjangoSessionRepository(ISessionRepository):

    def get_company_domain(self, company: object) -> Optional[str]:
        from platform.features.company.tenant.company.models import Domain
        domain = Domain.objects.filter(tenant=company).first()
        return domain.domain if domain else None

    def get_or_create_preferences(self, user: object) -> PreferencesSchema:
        from client.features.security.identity.identity.models import UserPreferences
        preferences, _ = UserPreferences.objects.get_or_create(user=user)
        return PreferencesSchema.model_validate(preferences)

    def get_active_subscription(self, company: object) -> Optional[SubscriptionInfoSchema]:
        from django.utils import timezone
        from platform.features.billing.subscription.subscription.models import CompanySubscription
        cs = (
            CompanySubscription.objects
            .filter(
                company=company,
                status__in=[
                    CompanySubscription.Status.ACTIVE,
                    CompanySubscription.Status.CANCELLED,
                    CompanySubscription.Status.SUSPENDED,
                ],
                end_date__gt=timezone.now(),
            )
            .select_related('subscription')
            .order_by('-start_date')
            .first()
        )
        if not cs:
            # Vigencia vencida o sin fila reciente: devolver la última adquisición
            # (p. ej. suspended tras fallo de cobro) para contexto en recovery.
            cs = (
                CompanySubscription.objects
                .filter(company=company)
                .select_related('subscription')
                .order_by('-start_date')
                .first()
            )
        if not cs:
            return None
        from platform.features.billing.subscription.subscription.domain.billing_cycle import (
            normalize_billing_interval,
        )
        return SubscriptionInfoSchema(
            id=str(cs.subscription.id),
            name=cs.subscription.name,
            end_date=cs.end_date.strftime('%d/%m/%Y'),
            status=cs.status,
            billing_interval=normalize_billing_interval(cs.billing_interval),
        )

    def build_billing_recovery_menu(self, rol: object) -> Tuple[list[MenuItemSchema], list[str]]:
        """Menú mínimo: módulo settings + features de facturación del rol."""
        from platform.features.security.access.modules.models import Module
        from client.features.security.lifecycle.registration.models import RolFeature
        from core.module_codes import normalize_module_route

        if not rol:
            return [], []

        rol_features = (
            RolFeature.objects
            .filter(rol=rol, feature__is_active=True)
            .select_related('feature')
        )
        features = [
            rf.feature.key for rf in rol_features
            if rf.feature.key in BILLING_RECOVERY_FEATURES
        ]

        module = Module.objects.filter(
            code=BILLING_RECOVERY_MODULE_CODE,
            is_active=True,
            is_sidebar=True,
        ).select_related('section').first()
        if not module or not (module.route or '').strip():
            return [], features

        menu = [
            MenuItemSchema(
                id=str(module.id),
                code=module.code,
                name=module.name,
                icon=module.icon,
                route=normalize_module_route(module.route),
                section=module.section.code,
                section_name=module.section.name,
            )
        ]
        return menu, features

    def build_menu(self, rol: object, subscription_id: str = None, company_id: str = None) -> Tuple[list[MenuItemSchema], list[str]]:
        from platform.features.security.access.modules.models import Module
        from client.features.security.lifecycle.registration.models import RolFeature, RolModule

        if not rol:
            return [], []

        # ── 1. Acceso por rol ─────────────────────────────────────────
        rol_features = (
            RolFeature.objects
            .filter(rol=rol, feature__is_active=True)
            .select_related('feature', 'feature__module')
        )
        features = [rf.feature.key for rf in rol_features]
        feature_module_codes = list(dict.fromkeys(rf.feature.module.code for rf in rol_features))

        direct_module_codes = list(
            RolModule.objects.filter(rol=rol).values_list('module_code', flat=True)
        )

        allowed_codes = list(dict.fromkeys(feature_module_codes + direct_module_codes))

        complement_keys: set[str] = set()
        complement_modules: set[str] = set()
        if company_id:
            from platform.features.billing.complement.entitlement.infrastructure.active import (
                active_complement_access,
            )
            complement_keys, complement_modules = active_complement_access(company_id)

        from core.access.enforcement import ADMIN_ROLE_NAME
        if company_id and getattr(rol, 'name', None) == ADMIN_ROLE_NAME:
            features = list(dict.fromkeys([*features, *complement_keys]))
            allowed_codes = list(dict.fromkeys([*allowed_codes, *complement_modules]))

        from core.module_codes import (
            canonicalize_module_codes,
            filter_codes_in_set_case_insensitive,
            normalize_module_route,
        )

        allowed_codes = canonicalize_module_codes(allowed_codes)

        # ── 2. Intersección con suscripción ───────────────────────────
        if subscription_id:
            from platform.features.billing.subscription.subscription.models import (
                SubscriptionModule, SubscriptionFunctionality,
            )
            sub_module_codes = set(
                SubscriptionModule.objects.filter(
                    subscription_id=subscription_id,
                ).values_list('module_code', flat=True)
            )
            sub_feature_keys = set(
                SubscriptionFunctionality.objects.filter(
                    subscription_id=subscription_id,
                    functionality__is_active=True,
                ).values_list('functionality__key', flat=True)
            )

            ceiling_modules = sub_module_codes | complement_modules
            ceiling_features = sub_feature_keys | complement_keys
            # Módulos y features del rol que el plan o un complemento habilitan.
            allowed_codes = filter_codes_in_set_case_insensitive(allowed_codes, ceiling_modules)
            features = [f for f in features if f in ceiling_features]

        # ── 3. Construir menú ─────────────────────────────────────────
        module_map = {
            m.code: m
            for m in Module.objects.filter(
                code__in=allowed_codes,
                is_active=True,
                is_sidebar=True,
                section__is_active=True,
            ).select_related('section')
        }
        menu = sorted(
            [
                MenuItemSchema(
                    id=str(module_map[code].id),
                    code=code,
                    name=module_map[code].name,
                    icon=module_map[code].icon,
                    route=normalize_module_route(module_map[code].route),
                    section=module_map[code].section.code,
                    section_name=module_map[code].section.name,
                )
                for code in allowed_codes
                if code in module_map and (module_map[code].route or '').strip()
            ],
            key=lambda item: (module_map[item.code].section.order, module_map[item.code].order),
        )
        return menu, features
