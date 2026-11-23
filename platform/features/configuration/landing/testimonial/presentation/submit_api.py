"""Company-user submit endpoint (tenant JWT)."""

import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.audit import audit_log
from core.auth.cookie_authentication import JWTAccessAuthentication
from core.decorators.response import wrap_response
from core.errors import AppException
from core.validators import validated_body

from platform.features.configuration.landing.testimonial.application.prompt_use_cases import (
    AckTestimonialPromptUseCase,
)
from platform.features.configuration.landing.testimonial.application.use_cases import (
    SubmitMyTestimonialUseCase,
)
from platform.features.configuration.landing.testimonial.domain.schemas import (
    SubmitMyTestimonialSchema,
    project_public,
)
from platform.features.configuration.landing.testimonial.infrastructure.repositories import (
    DjangoTestimonialPromptReceiptRepository,
    DjangoTestimonialRepository,
)
from platform.features.configuration.landing.testimonial.presentation.bodies import (
    SubmitMyTestimonialBody,
)

logger = logging.getLogger('app.api')


class SubmitMyTestimonialAPIView(APIView):
    """``POST /api/v1/testimonials/`` — the signed-in user posts their quote."""

    authentication_classes = [JWTAccessAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(SubmitMyTestimonialBody)
    def post(self, request, *args, body: dict, **kwargs):
        tenant_id = getattr(request.user, 'company_id', None)
        result = SubmitMyTestimonialUseCase(
            DjangoTestimonialRepository(),
        ).execute(
            SubmitMyTestimonialSchema(
                author_id=request.user.pk,
                tenant_id=str(tenant_id) if tenant_id else None,
                ip_address=request.META.get('REMOTE_ADDR') or None,
                user_agent=request.META.get('HTTP_USER_AGENT') or None,
                request_id=getattr(request, 'request_id', None),
                channel='web',
                **body,
            ),
        )
        audit_log(
            request, 'Testimonial', result.id, 'CREATE',
            f'Testimonial submitted by author {result.author_id}',
        )
        try:
            AckTestimonialPromptUseCase(
                DjangoTestimonialPromptReceiptRepository(),
            ).execute(request.user.pk)
        except AppException:
            logger.warning(
                'testimonial prompt ack after submit failed',
                exc_info=True,
            )
        public = project_public(result)
        return wrap_response(public.model_dump(mode='json'), status_code=201)
