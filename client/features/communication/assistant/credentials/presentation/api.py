"""API BYOK del assistant (settings del tenant)."""

from __future__ import annotations

import uuid

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from pydantic import ValidationError

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, ValidationAppException
from core.permissions import IsCompanyMember
from core.validators import validated_body

from client.features.communication.assistant.credentials.application.use_cases import (
    CreateCredentialUseCase,
    DeleteCredentialUseCase,
    ListCredentialsUseCase,
    UpdateCredentialUseCase,
)
from client.features.communication.assistant.credentials.domain.schemas import (
    CreateCredentialSchema,
    UpdateCredentialSchema,
)
from client.features.communication.assistant.credentials.infrastructure.repositories import (
    DjangoAssistantCredentialRepository,
)
from client.features.communication.assistant.credentials.presentation.bodies import (
    CreateCredentialBody,
    UpdateCredentialBody,
)


def _repo():
    return DjangoAssistantCredentialRepository()


# Temporal: sin HasSubscriptionAccess hasta el pase final de permisos.
_PERMS = [IsAuthenticated, IsCompanyMember]


class AssistantCredentialListCreateView(APIView):
    permission_classes = _PERMS

    def get(self, request, *args, **kwargs):
        items = ListCredentialsUseCase(_repo()).execute()
        return wrap_response([item.model_dump(mode='json') for item in items])

    @validated_body(CreateCredentialBody)
    def post(self, request, *args, body: dict, **kwargs):
        schema = CreateCredentialSchema(
            **body,
            created_by=getattr(request.user, 'id', None),
        )
        result = CreateCredentialUseCase(_repo()).execute(schema)
        audit_log(
            request,
            'AssistantProviderCredential',
            result.id,
            'CREATE',
            f'BYOK {result.provider} ···{result.key_last4}',
        )
        return wrap_response(result.model_dump(mode='json'), status_code=201)


class AssistantCredentialDetailView(APIView):
    permission_classes = _PERMS

    @validated_body(UpdateCredentialBody)
    def patch(self, request, credential_id, *args, body: dict, **kwargs):
        try:
            schema = UpdateCredentialSchema(**body)
        except ValidationError as exc:
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail='At least one of api_key, label, is_active is required.',
            ) from exc
        result = UpdateCredentialUseCase(_repo()).execute(
            uuid.UUID(str(credential_id)),
            schema,
        )
        audit_log(
            request,
            'AssistantProviderCredential',
            result.id,
            'UPDATE',
            changes={'provider': result.provider, 'is_active': result.is_active},
        )
        return wrap_response(result.model_dump(mode='json'))

    def delete(self, request, credential_id, *args, **kwargs):
        cid = uuid.UUID(str(credential_id))
        DeleteCredentialUseCase(_repo()).execute(cid)
        audit_log(request, 'AssistantProviderCredential', cid, 'DELETE')
        return wrap_response({'deleted': True})
