"""Public landing section visibility for base-landing-web (anonymous)."""

from rest_framework.views import APIView

from core.decorators.response import wrap_response
from platform.features.configuration.landing.landing.application.use_cases import (
    GetPublicLandingSectionsUseCase,
)
from platform.features.configuration.landing.landing.infrastructure.repositories import (
    DjangoLandingSectionRepository,
)


class PublicLandingSectionsAPIView(APIView):
    """``GET /api/v1/landing/sections/`` — map of section key → visible."""

    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        result = GetPublicLandingSectionsUseCase(
            DjangoLandingSectionRepository(),
        ).execute()
        return wrap_response(result.model_dump())
