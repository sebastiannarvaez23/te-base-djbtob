import uuid
from types import SimpleNamespace

import pytest

from platform.features.billing.commerce.refund.presentation.api import _company_id, _schema_name

pytestmark = pytest.mark.unit


def test_company_id_prefers_jwt_user():
    company_id = uuid.uuid4()
    request = SimpleNamespace(
        user=SimpleNamespace(company_id=company_id),
        tenant=SimpleNamespace(id=uuid.uuid4()),
    )
    assert _company_id(request) == company_id


def test_schema_name_prefers_user_company():
    request = SimpleNamespace(
        user=SimpleNamespace(company=SimpleNamespace(schema_name='acme')),
        tenant=SimpleNamespace(schema_name='public'),
    )
    assert _schema_name(request) == 'acme'
