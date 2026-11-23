from types import SimpleNamespace

import pytest

from client.features.communication.messaging.inbox.presentation.schema import schema_name_for_request

pytestmark = pytest.mark.unit


def test_schema_name_prefers_user_company():
    request = SimpleNamespace(
        user=SimpleNamespace(company=SimpleNamespace(schema_name='acme')),
        tenant=SimpleNamespace(schema_name='public'),
    )
    assert schema_name_for_request(request) == 'acme'


def test_schema_name_falls_back_to_tenant():
    request = SimpleNamespace(
        user=SimpleNamespace(company=None),
        tenant=SimpleNamespace(schema_name='acme'),
    )
    assert schema_name_for_request(request) == 'acme'
