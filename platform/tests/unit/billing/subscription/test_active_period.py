"""DjangoActivePeriodLookup returns a schema, never the ORM row."""
import uuid
from unittest.mock import MagicMock, patch

import pytest

from platform.features.billing.subscription.subscription.domain.schemas import ActivePeriodSchema
from platform.features.billing.subscription.subscription.infrastructure.active_period import (
    DjangoActivePeriodLookup,
)

pytestmark = pytest.mark.unit

_CS = 'platform.features.billing.subscription.subscription.infrastructure.active_period.CompanySubscription'


def _qs(first):
    qs = MagicMock()
    qs.order_by.return_value.only.return_value.first.return_value = first
    return qs


@patch(_CS)
def test_get_returns_active_period_schema(MockCS):
    company_id = uuid.uuid4()
    period_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    MockCS.Status.ACTIVE = 'active'
    row = MagicMock(id=period_id, subscription_id=plan_id, status='active')
    MockCS.objects.filter.return_value = _qs(row)

    result = DjangoActivePeriodLookup().get(company_id)

    MockCS.objects.filter.assert_called_once_with(
        company_id=company_id, status='active',
    )
    assert isinstance(result, ActivePeriodSchema)
    assert result.id == period_id
    assert result.subscription_id == plan_id
    assert result.status == 'active'


@patch(_CS)
def test_get_returns_none_when_no_active_period(MockCS):
    MockCS.Status.ACTIVE = 'active'
    MockCS.objects.filter.return_value = _qs(None)
    assert DjangoActivePeriodLookup().get(uuid.uuid4()) is None
