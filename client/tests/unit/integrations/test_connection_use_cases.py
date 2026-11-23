"""Matriz escenarios 19 — TestConnection."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from core.errors import AppErrorCode
from core.errors.exceptions import ServerException

from client.features.integrations.connections.profile.application.connection_use_cases import TestConnectionUseCase
from client.features.integrations.connections.profile.domain.schemas import ConnectionSchema
from core.integrations.infrastructure.fake_connector import FakeConnector


@pytest.mark.unit
class TestTestConnectionUseCase:

    def test_failed_test_connection_raises_int_002(self):
        conn_id = uuid.uuid4()
        connection = ConnectionSchema(
            id=conn_id,
            connector_key='fake',
            name='T',
            environment='CLIENT_TEST',
            config={'base_url': 'http://x'},
            status='ACTIVE',
        )
        profile = __import__(
            'core.integrations.domain.schemas', fromlist=['ConnectionProfile'],
        ).ConnectionProfile(
            connection_id=conn_id,
            tenant_schema='tenant',
            provider=__import__(
                'core.integrations.domain.enums', fromlist=['ConnectorProvider'],
            ).ConnectorProvider.FAKE,
            kind=__import__(
                'core.integrations.domain.enums', fromlist=['ConnectorKind'],
            ).ConnectorKind.ERP,
            environment=__import__(
                'core.integrations.domain.enums', fromlist=['Environment'],
            ).Environment.CLIENT_TEST,
            config={'base_url': 'http://x'},
        )

        with patch(
            'client.features.integrations.connections.profile.application.connection_use_cases.DjangoConnectionRepository',
        ) as repo_cls, patch(
            'client.features.integrations.connections.profile.application.connection_use_cases.build_connection_profile',
            return_value=profile,
        ), patch(
            'client.features.integrations.connections.profile.application.connection_use_cases.get_connector',
            return_value=FakeConnector(fail_on_test=True),
        ):
            repo_cls.return_value.get_by_id.return_value = connection
            with pytest.raises(ServerException) as exc:
                TestConnectionUseCase().execute(conn_id, 'tenant')
        assert exc.value.code == AppErrorCode.INT_CONNECTION_FAILED
