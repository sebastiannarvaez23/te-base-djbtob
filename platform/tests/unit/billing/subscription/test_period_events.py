"""Bus de eventos del ciclo de período (PeriodClosed / PeriodIssued).

Aislado del singleton de módulo para no interferir con listeners de apps.py.
"""
import logging
import uuid
from unittest.mock import patch

import pytest

from platform.features.billing.subscription.subscription.domain.events import (
    PeriodClosed,
    PeriodIssued,
    _EventBus,
    bus,
)

pytestmark = pytest.mark.unit


def _issued(**overrides) -> PeriodIssued:
    defaults = dict(
        company_id=uuid.uuid4(),
        period_id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
    )
    defaults.update(overrides)
    return PeriodIssued(**defaults)


def _closed(**overrides) -> PeriodClosed:
    defaults = dict(company_id=uuid.uuid4(), period_id=uuid.uuid4())
    defaults.update(overrides)
    return PeriodClosed(**defaults)


@pytest.fixture
def fresh_bus():
    return _EventBus()


def test_handler_receives_matching_event(fresh_bus):
    received = []
    fresh_bus.subscribe(PeriodIssued, received.append)
    evt = _issued()
    fresh_bus.publish(evt)
    assert received == [evt]


def test_publish_with_no_subscribers_is_a_noop(fresh_bus):
    fresh_bus.publish(_issued())


def test_period_closed_does_not_invoke_issued_handlers(fresh_bus):
    issued, closed = [], []
    fresh_bus.subscribe(PeriodIssued, issued.append)
    fresh_bus.subscribe(PeriodClosed, closed.append)
    fresh_bus.publish(_closed())
    assert issued == []
    assert len(closed) == 1


def test_subscribe_same_handler_twice_is_idempotent(fresh_bus):
    received = []

    def handler(e):
        received.append(e)

    fresh_bus.subscribe(PeriodIssued, handler)
    fresh_bus.subscribe(PeriodIssued, handler)
    fresh_bus.publish(_issued())
    assert len(received) == 1


def test_handler_exception_does_not_propagate(fresh_bus, caplog):
    def boom(e):
        raise RuntimeError('handler down')

    fresh_bus.subscribe(PeriodIssued, boom)
    with caplog.at_level(logging.ERROR, logger='billing.subscription.events'):
        fresh_bus.publish(_issued())
    assert any('failed' in r.message for r in caplog.records)


def test_handler_exception_does_not_stop_subsequent_handlers(fresh_bus, caplog):
    received = []

    def boom(e):
        raise ValueError('nope')

    fresh_bus.subscribe(PeriodIssued, boom)
    fresh_bus.subscribe(PeriodIssued, received.append)
    with caplog.at_level(logging.ERROR, logger='billing.subscription.events'):
        evt = _issued()
        fresh_bus.publish(evt)
    assert received == [evt]


def test_clear_drops_handlers(fresh_bus):
    received = []
    fresh_bus.subscribe(PeriodIssued, received.append)
    fresh_bus.clear()
    fresh_bus.publish(_issued())
    assert received == []


def test_module_bus_is_the_eventbus_instance():
    assert isinstance(bus, _EventBus)


def test_module_aliases_delegate_to_bus():
    from platform.features.billing.subscription.subscription.domain.events import publish, subscribe
    assert subscribe.__func__ is bus.subscribe.__func__
    assert publish.__func__ is bus.publish.__func__
    assert subscribe.__self__ is bus
    assert publish.__self__ is bus


def test_django_apps_subscribe_period_issued_listeners():
    from django.apps import apps
    from platform.features.billing.subscription.subscription.domain.events import PeriodIssued

    with patch(
        'platform.features.billing.subscription.subscription.domain.events.subscribe',
    ) as mock_subscribe:
        apps.get_app_config('payments').ready()
        apps.get_app_config('invoice').ready()

    period_calls = [
        c for c in mock_subscribe.call_args_list if c.args and c.args[0] is PeriodIssued
    ]
    handler_names = {c.args[1].__qualname__ for c in period_calls}
    assert 'PeriodIssuedChargeListener.on_period_issued' in handler_names
    assert 'PeriodIssuedInvoiceListener.on_period_issued' in handler_names
