"""Contracts of the billing-period Pydantic schemas."""
from datetime import datetime, timezone as tz
from uuid import uuid4

import pytest

from platform.features.billing.subscription.subscription.domain.schemas import (
    CompanySubscriptionResultSchema,
    PendingChangeSchema,
)

pytestmark = pytest.mark.unit

_START = datetime(2025, 6, 1, 12, 0, tzinfo=tz.utc)
_END = datetime(2025, 7, 1, 12, 0, tzinfo=tz.utc)


def test_result_end_date_is_display_label_from_ends_at():
    result = CompanySubscriptionResultSchema(
        id=uuid4(),
        subscription_id=uuid4(),
        subscription_name='Pro',
        start_date=_START,
        ends_at=_END,
        status='active',
    )
    assert result.end_date == '01/07/2025'
    dumped = result.model_dump()
    assert dumped['end_date'] == '01/07/2025'
    assert dumped['ends_at'] == _END


def test_result_status_is_normalized_to_lowercase():
    result = CompanySubscriptionResultSchema(
        id=uuid4(),
        subscription_id=uuid4(),
        subscription_name='Pro',
        start_date=_START,
        ends_at=_END,
        status='ACTIVE',
    )
    assert result.status == 'active'


def test_pending_change_defaults_monthly_interval():
    pending = PendingChangeSchema(
        type='downgrade',
        from_plan='Pro',
        to_plan='Std',
        activates_on=_END,
    )
    assert pending.billing_interval == 'monthly'


def test_pending_change_keeps_explicit_interval():
    pending = PendingChangeSchema(
        type='downgrade',
        from_plan='Pro',
        to_plan='Std',
        activates_on=_END,
        billing_interval='yearly',
    )
    assert pending.billing_interval == 'yearly'
