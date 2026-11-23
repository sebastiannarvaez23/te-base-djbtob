from __future__ import annotations

import uuid

from core.errors import AppErrorCode, ValidationAppException
from core.trace import trace_layer

from client.features.communication.assistant.credentials.domain.interfaces import (
    IAssistantCredentialRepository,
)
from client.features.communication.assistant.credentials.domain.schemas import (
    ActiveByokSchema,
    CreateCredentialSchema,
    CredentialPublicSchema,
    UpdateCredentialSchema,
)

_ALLOWED = frozenset({'openai', 'anthropic'})


def _normalize_provider(provider: str) -> str:
    name = (provider or '').strip().lower()
    if name not in _ALLOWED:
        raise ValidationAppException(
            AppErrorCode.VALIDATION_ERROR,
            override_detail='Provider must be openai or anthropic.',
        )
    return name


def _normalize_api_key(api_key: str) -> str:
    cleaned = (api_key or '').strip()
    if len(cleaned) < 8:
        raise ValidationAppException(
            AppErrorCode.VALIDATION_ERROR,
            override_detail='API key is too short.',
        )
    return cleaned


class ListCredentialsUseCase:
    def __init__(self, repository: IAssistantCredentialRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self) -> list[CredentialPublicSchema]:
        return self.repository.list_public()


class CreateCredentialUseCase:
    def __init__(self, repository: IAssistantCredentialRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, schema: CreateCredentialSchema) -> CredentialPublicSchema:
        provider = _normalize_provider(schema.provider)
        api_key = _normalize_api_key(schema.api_key)
        cleaned = schema.model_copy(update={
            'provider': provider,
            'api_key': api_key,
            'label': (schema.label or '').strip()[:120],
        })
        return self.repository.create(cleaned)


class UpdateCredentialUseCase:
    def __init__(self, repository: IAssistantCredentialRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self,
        credential_id: uuid.UUID,
        schema: UpdateCredentialSchema,
    ) -> CredentialPublicSchema:
        # Domain schema already requires ≥1 field; re-check for defense in depth.
        if schema.api_key is None and schema.label is None and schema.is_active is None:
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail='At least one of api_key, label, is_active is required.',
            )
        updates: dict = {}
        if schema.api_key is not None:
            updates['api_key'] = _normalize_api_key(schema.api_key)
        if schema.label is not None:
            updates['label'] = schema.label.strip()[:120]
        cleaned = schema.model_copy(update=updates) if updates else schema
        return self.repository.update(credential_id, cleaned)


class DeleteCredentialUseCase:
    def __init__(self, repository: IAssistantCredentialRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, credential_id: uuid.UUID) -> None:
        self.repository.delete(credential_id)


class ResolveActiveByokUseCase:
    """Resuelve clave activa para un provider concreto (sin exponerla por API)."""

    def __init__(self, repository: IAssistantCredentialRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, provider: str | None = None) -> ActiveByokSchema | None:
        if not provider:
            return None
        try:
            name = _normalize_provider(provider)
        except ValidationAppException:
            return None
        return self.repository.get_active_byok(name)
