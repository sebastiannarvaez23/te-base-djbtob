"""Construye ConnectionProfile desde persistencia."""

from __future__ import annotations

import uuid

from django.conf import settings

from client.features.integrations.connections.profile.domain.schemas import ConnectionSchema
from client.features.integrations.connections.profile.infrastructure.repositories import DjangoSecretRepository
from core.errors import AppErrorCode, ServerException, ValidationAppException
from core.integrations.domain.enums import ConnectorKind, ConnectorProvider, Environment
from core.integrations.domain.schemas import ConnectionProfile

_KEY_TO_PROVIDER = {
    'sap': ConnectorProvider.SAP,
    'siesa': ConnectorProvider.SIESA,
    'fake': ConnectorProvider.FAKE,
    'webhook-inbound': ConnectorProvider.WEBHOOK_INBOUND,
}

_KEY_TO_KIND = {
    'sap': ConnectorKind.ERP,
    'siesa': ConnectorKind.ERP,
    'fake': ConnectorKind.ERP,
    'webhook-inbound': ConnectorKind.APP,
}


def connector_key_to_provider(key: str) -> ConnectorProvider:
    provider = _KEY_TO_PROVIDER.get(key)
    if not provider:
        raise ServerException(
            AppErrorCode.INT_CONNECTOR_NOT_FOUND,
            override_detail=f'Unknown connector key: {key}',
        )
    return provider


def build_connection_profile(
    connection: ConnectionSchema,
    tenant_schema: str,
    secrets: dict[str, str] | None = None,
    *,
    secret_id: uuid.UUID | None = None,
) -> ConnectionProfile:
    if connection.environment == 'PROSANDBOX':
        allow = getattr(settings, 'DEBUG', False) or getattr(settings, 'INTEGRATIONS_ALLOW_PROSANDBOX', False)
        if not allow:
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail='PROSANDBOX environment is not allowed in this deployment.',
            )

    if secrets is None and secret_id:
        secrets = DjangoSecretRepository().get_decrypted(secret_id)

    return ConnectionProfile(
        connection_id=connection.id,
        tenant_schema=tenant_schema,
        provider=connector_key_to_provider(connection.connector_key),
        kind=_KEY_TO_KIND.get(connection.connector_key, ConnectorKind.ERP),
        environment=Environment(connection.environment),
        config=connection.config or {},
        secrets=secrets or {},
    )
