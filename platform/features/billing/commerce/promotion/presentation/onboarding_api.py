from uuid import UUID

from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, OnboardingException
from core.validators import validated_body

from client.features.security.lifecycle.onboarding.infrastructure.onboarding_token_store import (
    RedisOnboardingTokenStore,
)
from client.features.security.lifecycle.onboarding.presentation.cookies import ONBOARDING_COOKIE

from platform.features.billing.commerce.promotion import composition
from platform.features.billing.commerce.promotion.presentation.bodies import (
    ApplyOnboardingVoucherBody,
    ValidateVoucherBody,
)


def _resolve_registration_id(request) -> UUID:
    token = request.COOKIES.get(ONBOARDING_COOKIE)
    registration_id = RedisOnboardingTokenStore().resolve(token) if token else None
    if registration_id is None:
        raise OnboardingException(AppErrorCode.ONBOARDING_INVALID_TOKEN)
    return registration_id


class OnboardingPromotionValidateView(APIView):
    authentication_classes = []
    permission_classes = []

    @validated_body(ValidateVoucherBody)
    def post(self, request, *, body: dict):
        registration_id = _resolve_registration_id(request)
        result = composition.build_validate_onboarding_use_case().execute(
            registration_id,
            serial=body['serial'],
            subscription_id=body['subscription_id'],
            billing_interval=body.get('billing_interval'),
        )
        return wrap_response(result.model_dump(mode='json'))


class OnboardingPromotionApplyView(APIView):
    authentication_classes = []
    permission_classes = []

    @validated_body(ApplyOnboardingVoucherBody)
    def post(self, request, *, body: dict):
        registration_id = _resolve_registration_id(request)
        state = composition.build_apply_onboarding_use_case().execute(
            registration_id,
            serial=body['serial'],
            subscription_id=body['subscription_id'],
            billing_interval=body.get('billing_interval'),
        )
        audit_log(
            request, 'CompanyRegistration', registration_id, 'PROMOTION_APPLIED',
            f'serial={body["serial"]}',
        )
        return wrap_response(state.model_dump(mode='json'), message='Promotion applied.')
