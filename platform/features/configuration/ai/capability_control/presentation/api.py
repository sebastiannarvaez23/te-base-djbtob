from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication

from platform.features.configuration.ai.capability_control.application.use_cases import (
    GetCapabilityControlUseCase,
    UpdateCapabilityControlUseCase,
)
from platform.features.configuration.ai.capability_control.infrastructure.repositories import (
    DjangoCapabilityControlRepository,
)
from platform.features.configuration.ai.capability_control.presentation.bodies import (
    UpdateCapabilityControlBody,
)


def _repo():
    return DjangoCapabilityControlRepository()


class CapabilityControlView(APIView):
    """``GET|PATCH /api/v1/platform/ai/capabilities/``."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        result = GetCapabilityControlUseCase(_repo()).execute()
        return wrap_response(result.model_dump(mode='json'))

    @validated_body(UpdateCapabilityControlBody)
    def patch(self, request, *args, body: dict, **kwargs):
        result = UpdateCapabilityControlUseCase(_repo()).execute(body)
        audit_log(
            request, 'CapabilityControlSettings', 'default', 'UPDATE',
            changes={'count': len(result.capabilities)},
        )
        return wrap_response(result.model_dump(mode='json'))
