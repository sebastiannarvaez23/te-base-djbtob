from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication

from platform.features.configuration.assistant.assistant.application.use_cases import (
    GetAssistantAdminSettingsUseCase,
    UpdateAssistantAdminSettingsUseCase,
)
from platform.features.configuration.assistant.assistant.infrastructure.adapters import (
    CoreRuntimeHealthProbe,
    NullAssistantUsageReader,
    TenantAssistantUsageReader,
)
from platform.features.configuration.assistant.assistant.infrastructure.repositories import (
    DjangoAssistantSettingsRepository,
)
from platform.features.configuration.assistant.assistant.presentation.bodies import (
    UpdateAssistantSettingsBody,
)


def _repo():
    return DjangoAssistantSettingsRepository()


def _health():
    return CoreRuntimeHealthProbe()


class AssistantSettingsView(APIView):
    """``GET|PATCH /api/v1/platform/assistant-settings/``."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        result = GetAssistantAdminSettingsUseCase(
            _repo(), _health(), TenantAssistantUsageReader(),
        ).execute()
        return wrap_response(result.model_dump(mode='json'))

    @validated_body(UpdateAssistantSettingsBody)
    def patch(self, request, *args, body: dict, **kwargs):
        result = UpdateAssistantAdminSettingsUseCase(
            _repo(), _health(), NullAssistantUsageReader(),
        ).execute(body)
        audit_log(
            request, 'AssistantSettings', 'default', 'UPDATE',
            changes={
                'enabled': result.enabled,
                'provider': result.provider,
            },
        )
        return wrap_response(result.model_dump(mode='json'))
