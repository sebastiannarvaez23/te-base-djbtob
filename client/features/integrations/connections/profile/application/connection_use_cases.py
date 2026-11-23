"""Use cases de conexiones tenant."""

from __future__ import annotations

import uuid

from django.conf import settings

from core.errors import AppErrorCode, NotFoundException, ServerException, ValidationAppException
from core.ids import uuid7
from core.integrations import OperationContext, run_connector_op
from core.integrations.config import get_connector
from core.integrations.infrastructure.idempotency import MemoryIdempotencyStore
from core.integrations.application.connector_runner import ConnectorRunner

from client.features.integrations.connections.profile.application.profile_builder import build_connection_profile
from client.features.integrations.connections.profile.domain.interfaces import IConnectionRepository, ISecretRepository
from client.features.integrations.connections.profile.domain.schemas import CreateConnectionSchema, UpdateConnectionSchema
from client.features.integrations.connections.profile.infrastructure.repositories import (
    DjangoConnectionRepository,
    DjangoFieldMappingRepository,
    DjangoIntegrationOrderRepository,
    DjangoSecretRepository,
    DjangoSyncRunRepository,
)
from platform.features.integrations.connector_catalog.connector_catalog.infrastructure.repositories import (
    DjangoConnectorCatalogRepository,
)
from core.trace import trace_layer


class ListConnectionsUseCase:
    def __init__(self, repository: IConnectionRepository | None = None):
        self.repository = repository or DjangoConnectionRepository()

    @trace_layer('application')
    def execute(self, query):
        return self.repository.list_all(query)


class CreateConnectionUseCase:
    def __init__(
        self,
        connection_repo: IConnectionRepository | None = None,
        secret_repo: ISecretRepository | None = None,
        catalog_repo=None,
    ):
        self.connection_repo = connection_repo or DjangoConnectionRepository()
        self.secret_repo = secret_repo or DjangoSecretRepository()
        self.catalog_repo = catalog_repo or DjangoConnectorCatalogRepository()

    @trace_layer('application')
    def execute(self, data: CreateConnectionSchema, tenant_schema: str):
        definition = self.catalog_repo.get_by_key(data.connector_key)
        if not definition or not definition.is_active:
            raise ValidationAppException(
                AppErrorCode.INT_CONNECTOR_NOT_FOUND,
                override_detail=f"Connector '{data.connector_key}' is not available.",
            )
        if data.environment == 'PROSANDBOX':
            allow = getattr(settings, 'DEBUG', False) or getattr(settings, 'INTEGRATIONS_ALLOW_PROSANDBOX', False)
            if not allow:
                raise ValidationAppException(
                    AppErrorCode.VALIDATION_ERROR,
                    override_detail='PROSANDBOX is not allowed.',
                )

        secret_id = None
        if data.secrets:
            scope = f'{tenant_schema}:new'
            secret_id = self.secret_repo.store_encrypted(scope, data.secrets)

        return self.connection_repo.create(data, secret_id)


class UpdateConnectionUseCase:
    def __init__(
        self,
        connection_repo: IConnectionRepository | None = None,
        secret_repo: ISecretRepository | None = None,
    ):
        self.connection_repo = connection_repo or DjangoConnectionRepository()
        self.secret_repo = secret_repo or DjangoSecretRepository()

    @trace_layer('application')
    def execute(self, connection_id: uuid.UUID, data: UpdateConnectionSchema, tenant_schema: str):
        connection = self.connection_repo.get_by_id(connection_id)
        if not connection:
            raise NotFoundException(
                AppErrorCode.INT_CONNECTOR_NOT_FOUND,
                override_detail='Connection not found.',
            )
        if data.secrets:
            from client.features.integrations.connections.profile.models import IntegrationConnection
            model = IntegrationConnection.objects.filter(id=connection_id).first()
            scope = f'{tenant_schema}:{connection_id}'
            if model and model.secret_id:
                self.secret_repo.rotate(model.secret_id, scope, data.secrets)
            elif model:
                secret_id = self.secret_repo.store_encrypted(scope, data.secrets)
                model.secret_id = secret_id
                model.save(update_fields=['secret_id'])
            data = data.model_copy(update={'secrets': None})

        updated = self.connection_repo.update(connection_id, data)
        if not updated:
            raise NotFoundException(
                AppErrorCode.INT_CONNECTOR_NOT_FOUND,
                override_detail='Connection not found.',
            )
        return updated


class TestConnectionUseCase:
    @trace_layer('application')
    def execute(self, connection_id: uuid.UUID, tenant_schema: str, request_id: str = '-'):
        connection = DjangoConnectionRepository().get_by_id(connection_id)
        if not connection:
            raise NotFoundException(
                AppErrorCode.INT_CONNECTOR_NOT_FOUND,
                override_detail='Connection not found.',
            )
        profile = build_connection_profile(
            connection, tenant_schema, secret_id=connection.secret_id,
        )
        connector = get_connector(profile)
        ctx = OperationContext(
            connection_id=connection_id,
            tenant_schema=tenant_schema,
            operation='test_connection',
            request_id=request_id,
            idempotency_key=f'test:{uuid7()}',
        )
        runner = ConnectorRunner(idempotency_store=MemoryIdempotencyStore())
        result = run_connector_op(connector.test_connection, profile, context=ctx, runner=runner)
        if not result.ok:
            raise ServerException(
                AppErrorCode.INT_CONNECTION_FAILED,
                override_detail=result.message,
            )
        return result
