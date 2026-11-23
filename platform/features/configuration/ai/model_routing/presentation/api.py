from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication

from platform.features.configuration.ai.model_routing.application.use_cases import (
    GetModelRoutingAdminUseCase,
    UpdateModelRoutingAdminUseCase,
)
from platform.features.configuration.ai.model_routing.infrastructure.repositories import (
    DjangoModelRoutingRepository,
)
from platform.features.configuration.ai.model_routing.presentation.bodies import (
    UpdateModelRoutingBody,
)


def _repo():
    return DjangoModelRoutingRepository()


class ModelRoutingSettingsView(APIView):
    """``GET|PATCH /api/v1/platform/ai/model-routing/``."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        result = GetModelRoutingAdminUseCase(_repo()).execute()
        return wrap_response(result.model_dump(mode='json'))

    @validated_body(UpdateModelRoutingBody)
    def patch(self, request, *args, body: dict, **kwargs):
        result = UpdateModelRoutingAdminUseCase(_repo()).execute(body)
        audit_log(
            request, 'ModelRoutingSettings', 'default', 'UPDATE',
            changes={'route_count': len(result.routes)},
        )
        return wrap_response(result.model_dump(mode='json'))
