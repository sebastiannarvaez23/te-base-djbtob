"""Matriz escenarios 23–25 — connector catalog y health."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from core.errors.exceptions import ValidationAppException

from platform.features.integrations.connector_catalog.connector_catalog.application.health import GetIntegrationHealthUseCase
from platform.features.integrations.connector_catalog.connector_catalog.application.use_cases import (
    CreateConnectorDefinitionUseCase,
    DeleteConnectorDefinitionUseCase,
    ListConnectorDefinitionsUseCase,
    UpdateConnectorDefinitionUseCase,
)
from platform.features.integrations.connector_catalog.connector_catalog.domain.schemas import (
    ConnectorDefinitionSchema,
    CreateConnectorDefinitionSchema,
    UpdateConnectorDefinitionSchema,
)
from client.features.integrations.connections.profile.application.connection_use_cases import CreateConnectionUseCase
from client.features.integrations.connections.profile.domain.schemas import CreateConnectionSchema


class InMemoryCatalogRepo:
    def __init__(self):
        self.items: list[ConnectorDefinitionSchema] = []

    def get_all(self, *, active_only=False):
        rows = self.items
        if active_only:
            rows = [r for r in rows if r.is_active]
        return rows

    def get_by_id(self, id):
        return next((r for r in self.items if r.id == id), None)

    def get_by_key(self, key):
        return next((r for r in self.items if r.key == key), None)

    def create(self, data):
        row = ConnectorDefinitionSchema(id=uuid.uuid4(), **data.model_dump())
        self.items.append(row)
        return row

    def update(self, id, data):
        row = self.get_by_id(id)
        if not row:
            return None
        updated = row.model_copy(update=data.model_dump(exclude_unset=True))
        self.items = [updated if r.id == id else r for r in self.items]
        return updated

    def delete(self, id):
        before = len(self.items)
        self.items = [r for r in self.items if r.id != id]
        return len(self.items) < before


class InMemoryConnectionRepo:
    def create(self, data, secret_ref_id):
        from client.features.integrations.connections.profile.domain.schemas import ConnectionSchema
        return ConnectionSchema(
            id=uuid.uuid4(),
            connector_key=data.connector_key,
            name=data.name,
            environment=data.environment,
            config=data.config,
            status='ACTIVE',
            secret_id=secret_ref_id,
        )


class InMemorySecretRepo:
    def store_encrypted(self, scope, secrets):
        return uuid.uuid4()


@pytest.mark.unit
class TestConnectorCatalogCrud:

    def test_create_update_delete(self):
        repo = InMemoryCatalogRepo()
        created = CreateConnectorDefinitionUseCase(repo).execute(
            CreateConnectorDefinitionSchema(key='sap', kind='ERP', name='SAP'),
        )
        updated = UpdateConnectorDefinitionUseCase(repo).execute(
            created.id,
            UpdateConnectorDefinitionSchema(name='SAP ERP'),
        )
        assert updated.name == 'SAP ERP'
        DeleteConnectorDefinitionUseCase(repo).execute(created.id)
        assert ListConnectorDefinitionsUseCase(repo).execute() == []

    def test_inactive_connector_blocks_tenant_connection(self):
        catalog = InMemoryCatalogRepo()
        catalog.items.append(
            ConnectorDefinitionSchema(
                id=uuid.uuid4(), key='sap', kind='ERP', name='SAP', is_active=False,
            )
        )
        with pytest.raises(ValidationAppException):
            CreateConnectionUseCase(
                connection_repo=InMemoryConnectionRepo(),
                secret_repo=InMemorySecretRepo(),
                catalog_repo=catalog,
            ).execute(
                CreateConnectionSchema(
                    connector_key='sap', name='Conn', environment='CLIENT_TEST',
                ),
                'tenant_a',
            )


@pytest.mark.unit
class TestIntegrationHealth:

    def test_health_counts_degraded_connections(self):
        tenant = MagicMock(schema_name='acme', name='Acme')

        class Qs:
            def values(self, *args, **kwargs):
                return self

            def __getitem__(self, sl):
                return [
                    {
                        'id': uuid.uuid4(),
                        'name': 'SAP Prod',
                        'connector_key': 'sap',
                        'environment': 'CLIENT_PROD',
                        'status': 'DEGRADED',
                        'last_error': 'timeout',
                    },
                ]

        with patch(
            'platform.features.integrations.connector_catalog.connector_catalog.application.health.get_tenant_model',
        ) as get_model, patch(
            'platform.features.integrations.connector_catalog.connector_catalog.application.health.schema_context',
        ) as ctx, patch(
            'platform.features.integrations.connector_catalog.connector_catalog.application.health.IntegrationConnection',
        ) as conn_model:
            get_model.return_value.objects.exclude.return_value = [tenant]
            ctx.return_value.__enter__ = lambda s: None
            ctx.return_value.__exit__ = lambda s, *a: None
            conn_model.objects.values.return_value = Qs()

            result = GetIntegrationHealthUseCase().execute()

        assert result['summary']['degraded_connections'] == 1
        assert len(result['issues']) == 1
        assert result['issues'][0]['tenant_schema'] == 'acme'
