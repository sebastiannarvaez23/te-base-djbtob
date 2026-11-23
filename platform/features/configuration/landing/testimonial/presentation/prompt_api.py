from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.auth.cookie_authentication import JWTAccessAuthentication
from core.decorators.response import wrap_response

from platform.features.configuration.landing.testimonial.application.prompt_use_cases import (
    AckTestimonialPromptUseCase,
    DecideTestimonialPromptUseCase,
    RecordTestimonialPromptSeenUseCase,
)
from platform.features.configuration.landing.testimonial.infrastructure.repositories import (
    DjangoTestimonialPromptReceiptRepository,
    DjangoTestimonialPromptSettingsRepository,
    DjangoTestimonialRepository,
)


def _settings():
    return DjangoTestimonialPromptSettingsRepository()


def _receipts():
    return DjangoTestimonialPromptReceiptRepository()


def _testimonials():
    return DjangoTestimonialRepository()


class TestimonialPromptDecisionView(APIView):
    """``GET /api/v1/testimonials/prompt/`` — whether the client should ask now."""

    __test__ = False

    authentication_classes = [JWTAccessAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        result = DecideTestimonialPromptUseCase(
            _settings(), _receipts(), _testimonials(),
        ).execute(request.user.pk)
        return wrap_response(result.model_dump(mode='json'))


class RecordTestimonialPromptSeenView(APIView):
    """``POST /api/v1/testimonials/prompt/seen/`` — first-appearance clock."""

    authentication_classes = [JWTAccessAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        result = RecordTestimonialPromptSeenUseCase(_receipts()).execute(
            request.user.pk,
        )
        return wrap_response(result.model_dump(mode='json'))


class AckTestimonialPromptView(APIView):
    """``POST /api/v1/testimonials/prompt/ack/`` — skip / already shown."""

    authentication_classes = [JWTAccessAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        result = AckTestimonialPromptUseCase(_receipts()).execute(
            request.user.pk,
        )
        return wrap_response(result.model_dump(mode='json'))
