import uuid
from types import SimpleNamespace

import pytest

from platform.features.billing.subscription.subscription.presentation.api import _company_id

pytestmark = pytest.mark.unit


def test_company_id_prefers_jwt_company():
    company_id = uuid.uuid4()
    request = SimpleNamespace(
        user=SimpleNamespace(
            company_id=company_id,
            company=SimpleNamespace(id=company_id),
        ),
        tenant=SimpleNamespace(id=uuid.uuid4()),
    )
    assert _company_id(request) == company_id
