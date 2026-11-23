"""Unit tests — Integration Application model helpers (no DB)."""
import pytest

from client.features.integrations.oauth.client.models import IntegrationApplication


@pytest.mark.unit
def test_str_shows_name_and_client_id():
    app = IntegrationApplication(name='ERP bridge', client_id='wa_abc123')
    assert str(app) == 'ERP bridge (wa_abc123)'


@pytest.mark.unit
def test_primary_key_defaults_to_uuid7():
    assert IntegrationApplication().id.version == 7
