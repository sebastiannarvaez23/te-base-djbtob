from uuid import UUID

from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, OnboardingException

from django.conf import settings

from ..application.use_cases.check_username import CheckUsernameAvailabilityUseCase
from ..application.use_cases.get_state import GetOnboardingStateUseCase
from ..application.use_cases.resend_resume_link import ResendOnboardingResumeLinkUseCase
from ..application.use_cases.resume import ResumeOnboardingUseCase
from ..application.use_cases.start import StartOnboardingUseCase
from ..application.use_cases.submit_admin_user import SubmitAdminUserStepUseCase
from ..application.use_cases.submit_company import SubmitCompanyStepUseCase
from ..application.use_cases.submit_payment import SubmitPaymentStepUseCase
from ..application.use_cases.submit_subscription import SubmitSubscriptionStepUseCase
from ..domain.schemas import (
    AdminUserStepSchema,
    CompanyStepSchema,
    PaymentStepSchema,
    SubscriptionStepSchema,
)
from core.parameters import get_parameter
from core.query import validated_query
from core.validators import validated_body

from ..infrastructure.onboarding_token_store import (
    RedisOnboardingResumeTokenStore, RedisOnboardingTokenStore,
)
from ..infrastructure.finalize_composition import compose_finalize_use_case
from ..infrastructure.plan_catalog import DjangoOnboardingPlanCatalog
from ..infrastructure.repositories import DjangoCompanyRegistrationRepository
from ..infrastructure.resume_throttle import CacheResumeLinkThrottle
from platform.features.company.tenant.company.infrastructure.repositories import (
    DjangoCompanyRepository,
)
from .bodies import (
    AdminUserStepBody,
    CheckUsernameBody,
    CompanyStepBody,
    FinalizeOnboardingBody,
    PaymentStepBody,
    ResendResumeLinkBody,
    ResumeOnboardingBody,
    StartOnboardingBody,
    SubscriptionStepBody,
)
from .cookies import ONBOARDING_COOKIE, clear_onboarding_cookie, set_onboarding_cookie
from .queries import OnboardingPublishedPolicyQuery

# Defaults if the Parameter rows are absent. Seven days is enough to absorb
# weekend interruptions; the token TTL is shorter to limit replay window.
_DEFAULT_REGISTRATION_TTL_DAYS = 7
_DEFAULT_TOKEN_TTL_SECONDS = 2 * 3600


def _registration_ttl_seconds() -> int:
    days = int(get_parameter('ONB_REG_TTL_D', default=_DEFAULT_REGISTRATION_TTL_DAYS))
    return days * 24 * 3600


def _token_ttl_seconds() -> int:
    return int(get_parameter('ONB_TOK_TTL_S', default=_DEFAULT_TOKEN_TTL_SECONDS))


def _repo():
    return DjangoCompanyRegistrationRepository()


def _token_store():
    return RedisOnboardingTokenStore()


def _resume_token_store():
    return RedisOnboardingResumeTokenStore()


def _resume_throttle():
    return CacheResumeLinkThrottle()


def _resume_dispatcher(to_email: str, raw_token: str, ttl_seconds: int) -> None:
    """Adapter: translate use-case args into the dispatcher signature.

    Kept as a free function so the use case stays free of platform-layer
    imports.
    """
    from platform.features.communication.notification.dispatchers import (
        dispatch_onboarding_resume,
    )

    resume_url = f'{settings.ONB_RESUME_URL}?token={raw_token}'
    expires_in_days = max(1, ttl_seconds // 86400)
    dispatch_onboarding_resume(
        to_email=to_email,
        resume_url=resume_url,
        expires_in_days=expires_in_days,
    )


def _resolve_registration_id(request) -> UUID:
    """Read the cookie and map it to a registration_id, or raise."""
    token = request.COOKIES.get(ONBOARDING_COOKIE)
    registration_id = _token_store().resolve(token) if token else None
    if registration_id is None:
        raise OnboardingException(AppErrorCode.ONBOARDING_INVALID_TOKEN)
    return registration_id


class OnboardingStartAPIView(APIView):
    """Create a fresh onboarding session and issue the onboarding token cookie."""

    authentication_classes = []
    permission_classes = []

    @validated_body(StartOnboardingBody)
    def post(self, request, *, body: dict):

        token_ttl = _token_ttl_seconds()
        use_case = StartOnboardingUseCase(
            repository=_repo(),
            token_store=_token_store(),
            registration_ttl_seconds=_registration_ttl_seconds(),
            token_ttl_seconds=token_ttl,
            resume_token_store=_resume_token_store(),
            resume_dispatcher=_resume_dispatcher,
        )
        token, reg = use_case.execute(email=body['email'])

        audit_log(
            request, 'CompanyRegistration', reg.id, 'CREATE',
            f'Onboarding started for email={reg.email}',
        )
        response = wrap_response(
            {
                'registration_id': str(reg.id),
                'expires_at': reg.expires_at.isoformat(),
            },
            status_code=201,
            message='Onboarding started.',
        )
        return set_onboarding_cookie(response, token, max_age=token_ttl)


class OnboardingStateAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        registration_id = _resolve_registration_id(request)
        state = GetOnboardingStateUseCase(_repo()).execute(registration_id)
        return wrap_response(state.model_dump(mode='json'))


class _StepAPIView(APIView):
    """Base class for single-step POST endpoints."""
    authentication_classes = []
    permission_classes = []

    body_class = None
    schema_class = None
    step_name = None  # for audit

    def _build_schema(self, body_data: dict):
        return self.schema_class(**body_data)

    def _run(self, registration_id: UUID, schema):
        """Execute the use case and return its OnboardingStateSchema."""
        raise NotImplementedError

    def post(self, request):
        # Cookie first: an invalid session must 401 before body validation
        # (otherwise an empty body would leak 400 without a token).
        registration_id = _resolve_registration_id(request)
        data, err = self.body_class(request.data).parse()
        if err:
            return err

        schema = self._build_schema(data)
        state = self._run(registration_id, schema)

        audit_log(
            request, 'CompanyRegistration', registration_id, 'STEP_COMPLETED',
            f'step={self.step_name}',
        )
        return wrap_response(state.model_dump(mode='json'), message=f'Step {self.step_name} saved.')


class OnboardingCompanyAPIView(_StepAPIView):
    body_class = CompanyStepBody
    schema_class = CompanyStepSchema
    step_name = 'company'

    def _run(self, registration_id, schema):
        return SubmitCompanyStepUseCase(_repo(), DjangoCompanyRepository()).execute(
            registration_id, schema,
        )


class OnboardingCheckUsernameAPIView(APIView):
    """Probe whether a username is still free before the admin step is submitted."""

    authentication_classes = []
    permission_classes = []

    @validated_body(CheckUsernameBody)
    def post(self, request, *, body: dict):
        # Require an active onboarding session so this cannot be used as a
        # blind enumeration oracle without first starting registration.
        _resolve_registration_id(request)


        available = CheckUsernameAvailabilityUseCase(_repo()).execute(body['username'])
        return wrap_response({'available': available})


class OnboardingAdminUserAPIView(_StepAPIView):
    body_class = AdminUserStepBody
    schema_class = AdminUserStepSchema
    step_name = 'admin_user'

    def _run(self, registration_id, schema):
        return SubmitAdminUserStepUseCase(_repo()).execute(registration_id, schema)


class OnboardingSubscriptionAPIView(_StepAPIView):
    body_class = SubscriptionStepBody
    schema_class = SubscriptionStepSchema
    step_name = 'subscription'

    def _run(self, registration_id, schema):
        return SubmitSubscriptionStepUseCase(
            _repo(),
            DjangoOnboardingPlanCatalog(),
        ).execute(registration_id, schema)


class OnboardingPaymentAPIView(_StepAPIView):
    body_class = PaymentStepBody
    schema_class = PaymentStepSchema
    step_name = 'payment'

    def _run(self, registration_id, schema):
        return SubmitPaymentStepUseCase(_repo()).execute(registration_id, schema)


class OnboardingResumeAPIView(APIView):
    """Consume a magic-link resume token: validates, sets the cookie, returns 204.

    Single-use: the resume token is revoked after the cookie is issued.
    """

    authentication_classes = []
    permission_classes = []

    @validated_body(ResumeOnboardingBody)
    def post(self, request, *, body: dict):

        token_ttl = _token_ttl_seconds()
        session_token, registration_id = ResumeOnboardingUseCase(
            repository=_repo(),
            token_store=_token_store(),
            resume_token_store=_resume_token_store(),
            token_ttl_seconds=token_ttl,
        ).execute(body['token'])

        audit_log(
            request, 'CompanyRegistration', registration_id, 'RESUME',
            'Resumed via magic-link',
        )
        response = wrap_response(
            {'registration_id': str(registration_id)},
            message='Onboarding session restored.',
        )
        return set_onboarding_cookie(response, session_token, max_age=token_ttl)


class OnboardingResendResumeLinkAPIView(APIView):
    """Re-emit the magic-link for an in-progress onboarding.

    Used by the /register-start screen when the user re-enters an email
    that already has an active onboarding (ONB_005). Throttled per email
    via Redis. Rejects unknown emails to avoid enumeration.
    """

    authentication_classes = []
    permission_classes = []

    @validated_body(ResendResumeLinkBody)
    def post(self, request, *, body: dict):

        ResendOnboardingResumeLinkUseCase(
            repository=_repo(),
            resume_token_store=_resume_token_store(),
            resume_dispatcher=_resume_dispatcher,
            registration_ttl_seconds=_registration_ttl_seconds(),
            throttle=_resume_throttle(),
        ).execute(email=body['email'])

        audit_log(
            request, 'CompanyRegistration', None, 'RESUME_LINK_RESENT',
            f'Resent resume link for email={body["email"]}',
        )
        return wrap_response(
            {},
            status_code=204,
            message='Resume link sent.',
        )


class OnboardingFinalizeAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    @validated_body(FinalizeOnboardingBody)
    def post(self, request, *, body: dict):
        registration_id = _resolve_registration_id(request)

        from platform.features.compliance.policy.policy.domain.schemas import SignPolicyContextSchema

        result = compose_finalize_use_case(_repo()).execute(
            registration_id,
            privacy_accepted=bool(body['privacy_accepted']),
            privacy_content_hash=body['privacy_content_hash'],
            privacy_country=body['privacy_country'],
            terms_accepted=bool(body['terms_accepted']),
            terms_content_hash=body['terms_content_hash'],
            sign_context=SignPolicyContextSchema(
                ip_address=request.META.get('REMOTE_ADDR') or None,
                user_agent=request.META.get('HTTP_USER_AGENT') or None,
                request_id=getattr(request, 'request_id', None),
                channel='web',
            ),
        )

        audit_log(
            request, 'CompanyRegistration', registration_id, 'FINALIZE',
            f'company_id={result.company_id}',
        )
        # Invalidate the onboarding token once finalized.
        token = request.COOKIES.get(ONBOARDING_COOKIE)
        if token:
            _token_store().revoke(token)

        response = wrap_response(
            result.model_dump(mode='json'),
            status_code=201,
            message='Registration completed.',
        )
        return clear_onboarding_cookie(response)


class OnboardingPublishedPolicyAPIView(APIView):
    """Published policy markdown for the registration confirmation step.

    Only the single *published* version is returned (draft/approved/revoked
    are never exposed). Country comes from the query or the registration's
    ``company_data.country_code``.
    """

    authentication_classes = []
    permission_classes = []

    @validated_query(OnboardingPublishedPolicyQuery)
    def get(self, request, code: str, *args, query, **kwargs):
        from core.storage import MinioStorageService
        from platform.features.compliance.policy.policy.application.public_use_cases import (
            GetPublishedPolicyByCodeUseCase,
        )
        from platform.features.compliance.policy.policy.infrastructure.repositories import (
            DjangoPolicyRepository,
        )

        from ..application.privacy import resolve_registration_country_code

        country = (query.filters or {}).get('country')
        if country:
            country = str(country).strip().upper()
        if not country:
            registration_id = _resolve_registration_id(request)
            reg = _repo().get(registration_id)
            country = resolve_registration_country_code(
                getattr(reg, 'company_data', None) if reg else None,
            )
        if not country:
            raise OnboardingException(AppErrorCode.ONBOARDING_PRIVACY_STALE)

        content = GetPublishedPolicyByCodeUseCase(
            DjangoPolicyRepository(),
            MinioStorageService(),
        ).execute(code, country)

        return wrap_response({
            'policy_id': str(content.policy_id),
            'policy_code': content.policy_code,
            'country': content.country,
            'version': content.version,
            'status': content.status.value if hasattr(content.status, 'value') else content.status,
            'title': content.title,
            'markdown': content.markdown,
            'content_hash': content.content_hash,
        })
