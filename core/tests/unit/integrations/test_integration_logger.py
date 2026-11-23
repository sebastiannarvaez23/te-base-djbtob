"""Matriz escenario 13 — Integration logger enmascara secretos."""

from unittest.mock import MagicMock, patch

import pytest

from core.integrations.observability.integration_logger import log_integration_event


@pytest.mark.unit
class TestIntegrationLogger:

    def test_password_masked_before_persist(self):
        captured = {}

        def _save(context, data):
            captured['request_body'] = data.request_body

        mock_manager = MagicMock()
        mock_manager.integration.side_effect = _save

        with patch('client.features.logging.facade.factory.LogManagerFactory.create', return_value=mock_manager), \
             patch('client.features.logging.facade.context.LogContextBuilder.from_system', return_value=MagicMock()):
            log_integration_event(
                system='sap',
                direction='outbound',
                endpoint='pull_entities',
                method='POST',
                request_body={'username': 'admin', 'password': 's3cr3t'},
            )

        assert captured['request_body']['password'] == '***'
        assert captured['request_body']['username'] == 'admin'
