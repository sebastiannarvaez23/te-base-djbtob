"""Warehouse events persist and filter by the active subscription period."""
import uuid
from unittest.mock import MagicMock, patch

import pytest

from client.features.logging.facade.context import LogContext
from client.features.logging.ops.operations.domain.schemas import WarehouseEventInputSchema
from client.features.logging.ops.operations.infrastructure.repositories import (
    DjangoWarehouseEventRepository,
)

pytestmark = pytest.mark.unit

_MODEL = 'client.features.logging.ops.operations.models.WarehouseEvent'


def _context(**overrides) -> LogContext:
    defaults = dict(request_id='req-1')
    defaults.update(overrides)
    return LogContext(**defaults)


def _data() -> WarehouseEventInputSchema:
    return WarehouseEventInputSchema(
        event_type='RECEIVING_CONFIRMED',
        zone='A',
        location='A-01',
        reference_type='asn',
        reference_id='ASN-1',
        payload={'qty': 2},
    )


@patch(_MODEL)
def test_save_stamps_company_subscription_id(MockEvent):
    period_id = uuid.uuid4()
    DjangoWarehouseEventRepository().save(_context(company_subscription_id=period_id), _data())
    MockEvent.objects.create.assert_called_once()
    kwargs = MockEvent.objects.create.call_args.kwargs
    assert kwargs['company_subscription_id'] == period_id
    assert kwargs['event_type'] == 'RECEIVING_CONFIRMED'
    assert kwargs['request_id'] == 'req-1'


@patch(_MODEL)
def test_save_allows_missing_period(MockEvent):
    DjangoWarehouseEventRepository().save(_context(), _data())
    kwargs = MockEvent.objects.create.call_args.kwargs
    assert kwargs['company_subscription_id'] is None


@patch(_MODEL)
def test_query_filters_by_company_subscription_id(MockEvent):
    period_id = uuid.uuid4()
    qs = MagicMock()
    qs.__getitem__.return_value = ['row']
    MockEvent.objects.all.return_value = qs
    qs.filter.return_value = qs

    result = DjangoWarehouseEventRepository().query(
        {'company_subscription_id': period_id}, limit=10, offset=0,
    )

    qs.filter.assert_called_once_with(company_subscription_id=period_id)
    qs.__getitem__.assert_called_once_with(slice(0, 10))
    assert result == ['row']
