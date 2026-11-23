from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication

from platform.features.configuration.landing.testimonial.application.prompt_use_cases import (
    GetTestimonialPromptSettingsUseCase,
    RepromptTestimonialsUseCase,
    UpdateTestimonialPromptSettingsUseCase,
)
from platform.features.configuration.landing.testimonial.domain.schemas import (
    RepromptTestimonialsSchema,
    UpdateTestimonialPromptSettingsSchema,
)
from platform.features.configuration.landing.testimonial.infrastructure.repositories import (
    DjangoTestimonialPromptReceiptRepository,
    DjangoTestimonialPromptSettingsRepository,
    DjangoTestimonialRepository,
)
from platform.features.configuration.landing.testimonial.presentation.bodies import (
    RepromptTestimonialsBody,
    UpdateTestimonialPromptSettingsBody,
)


def _settings_repo():
    return DjangoTestimonialPromptSettingsRepository()


class TestimonialPromptSettingsView(APIView):
    """``GET/PATCH /api/v1/platform/testimonials/settings/``."""

    __test__ = False

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        result = GetTestimonialPromptSettingsUseCase(_settings_repo()).execute()
        return wrap_response(result.model_dump(mode='json'))

    @validated_body(UpdateTestimonialPromptSettingsBody)
    def patch(self, request, *args, body: dict, **kwargs):
        result = UpdateTestimonialPromptSettingsUseCase(_settings_repo()).execute(
            UpdateTestimonialPromptSettingsSchema(**body),
        )
        audit_log(
            request, 'TestimonialPromptSettings', 'default', 'UPDATE',
            changes=body,
        )
        return wrap_response(result.model_dump(mode='json'))


class RepromptTestimonialsView(APIView):
    """``POST /api/v1/platform/testimonials/reprompt/`` — ask selected authors again."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(RepromptTestimonialsBody)
    def post(self, request, *args, body: dict, **kwargs):
        result = RepromptTestimonialsUseCase(
            DjangoTestimonialRepository(),
            DjangoTestimonialPromptReceiptRepository(),
        ).execute(RepromptTestimonialsSchema(**body))
        audit_log(
            request, 'TestimonialPromptReceipt', 'reprompt', 'UPDATE',
            f'Testimonial prompt requested for {result.requested} authors',
        )
        return wrap_response(result.model_dump(mode='json'))
