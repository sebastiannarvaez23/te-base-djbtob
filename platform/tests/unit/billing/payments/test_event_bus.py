"""
Tests del bus de eventos del módulo de pagos.

Verifican subscribe/publish/unsubscribe, aislamiento por tipo de evento,
tolerancia a handlers que lanzan, e idempotencia de subscribe.
"""

import logging
import uuid
from datetime import datetime, timezone as tz
from decimal import Decimal

import pytest

from platform.features.billing.commerce.payments.domain.enums import GatewayProvider, MethodType
from platform.features.billing.commerce.payments.domain.events import (
    PaymentAuthorized,
    PaymentCanceled,
    PaymentCaptured,
    _EventBus,
    bus,
)


pytestmark = pytest.mark.unit


def _captured_event(**overrides) -> PaymentCaptured:
    defaults = dict(
        charge_id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        gateway_provider=GatewayProvider.SIMULATOR,
        occurred_at=datetime.now(tz.utc),
        amount=Decimal('100'),
        currency='COP',
        method_type=MethodType.CARD,
    )
    defaults.update(overrides)
    return PaymentCaptured(**defaults)


@pytest.fixture
def fresh_bus():
    """Cada test recibe un bus aislado para no interferir con suscripciones de apps.py."""
    return _EventBus()


# ── Suscripción y publicación básica ──────────────────────────────────────────


def test_handler_receives_event_published_to_same_type(fresh_bus):
    received = []
    fresh_bus.subscribe(PaymentCaptured, received.append)

    evt = _captured_event()
    fresh_bus.publish(evt)

    assert received == [evt]


def test_publish_with_no_subscribers_is_a_noop(fresh_bus):
    fresh_bus.publish(_captured_event())  # no debe lanzar


def test_handler_subscribed_to_different_event_is_not_called(fresh_bus):
    captured = []
    authorized = []
    fresh_bus.subscribe(PaymentCaptured, captured.append)
    fresh_bus.subscribe(PaymentAuthorized, authorized.append)

    fresh_bus.publish(_captured_event())

    assert len(captured) == 1
    assert authorized == []


def test_multiple_handlers_for_same_event_all_invoked(fresh_bus):
    h1, h2, h3 = [], [], []
    fresh_bus.subscribe(PaymentCaptured, h1.append)
    fresh_bus.subscribe(PaymentCaptured, h2.append)
    fresh_bus.subscribe(PaymentCaptured, h3.append)

    evt = _captured_event()
    fresh_bus.publish(evt)

    assert h1 == h2 == h3 == [evt]


def test_handlers_invoked_in_subscription_order(fresh_bus):
    order = []
    fresh_bus.subscribe(PaymentCaptured, lambda e: order.append('a'))
    fresh_bus.subscribe(PaymentCaptured, lambda e: order.append('b'))
    fresh_bus.subscribe(PaymentCaptured, lambda e: order.append('c'))

    fresh_bus.publish(_captured_event())

    assert order == ['a', 'b', 'c']


# ── Idempotencia de subscribe ────────────────────────────────────────────────


def test_subscribing_same_handler_twice_is_idempotent(fresh_bus):
    received = []

    def handler(e):
        received.append(e)

    fresh_bus.subscribe(PaymentCaptured, handler)
    fresh_bus.subscribe(PaymentCaptured, handler)
    fresh_bus.subscribe(PaymentCaptured, handler)

    fresh_bus.publish(_captured_event())

    assert len(received) == 1
    assert fresh_bus.handler_count(PaymentCaptured) == 1


def test_subscribing_same_function_via_different_bound_method_creates_two(fresh_bus):
    """Métodos enlazados de la misma instancia comparan igual; distintas instancias no."""
    class Listener:
        def __init__(self):
            self.received = []
        def handle(self, evt):
            self.received.append(evt)

    l1 = Listener()
    l2 = Listener()
    fresh_bus.subscribe(PaymentCaptured, l1.handle)
    fresh_bus.subscribe(PaymentCaptured, l2.handle)

    fresh_bus.publish(_captured_event())
    assert len(l1.received) == 1
    assert len(l2.received) == 1


# ── Desuscripción ────────────────────────────────────────────────────────────


def test_unsubscribe_removes_handler(fresh_bus):
    received = []

    def handler(e):
        received.append(e)

    fresh_bus.subscribe(PaymentCaptured, handler)
    fresh_bus.unsubscribe(PaymentCaptured, handler)
    fresh_bus.publish(_captured_event())

    assert received == []


def test_unsubscribe_unknown_handler_does_not_raise(fresh_bus):
    def handler(e):
        pass

    fresh_bus.unsubscribe(PaymentCaptured, handler)  # nunca se suscribió


def test_clear_removes_all_handlers(fresh_bus):
    fresh_bus.subscribe(PaymentCaptured, lambda e: None)
    fresh_bus.subscribe(PaymentAuthorized, lambda e: None)
    assert fresh_bus.handler_count(PaymentCaptured) == 1

    fresh_bus.clear()

    assert fresh_bus.handler_count(PaymentCaptured) == 0
    assert fresh_bus.handler_count(PaymentAuthorized) == 0


# ── Tolerancia a errores en handlers ─────────────────────────────────────────


def test_handler_exception_does_not_propagate_to_publisher(fresh_bus, caplog):
    def angry_handler(e):
        raise RuntimeError('boom')

    fresh_bus.subscribe(PaymentCaptured, angry_handler)

    with caplog.at_level(logging.ERROR, logger='payments.events'):
        fresh_bus.publish(_captured_event())  # no debe lanzar

    assert any('boom' in r.message or 'failed' in r.message for r in caplog.records)


def test_handler_exception_does_not_stop_subsequent_handlers(fresh_bus, caplog):
    received = []

    def angry(e):
        raise ValueError('nope')

    def good(e):
        received.append(e)

    fresh_bus.subscribe(PaymentCaptured, angry)
    fresh_bus.subscribe(PaymentCaptured, good)

    with caplog.at_level(logging.ERROR, logger='payments.events'):
        fresh_bus.publish(_captured_event())

    assert len(received) == 1


# ── handler_count ────────────────────────────────────────────────────────────


def test_handler_count_for_unknown_event_is_zero(fresh_bus):
    assert fresh_bus.handler_count(PaymentCanceled) == 0


def test_handler_count_reflects_current_subscriptions(fresh_bus):
    h1 = lambda e: None
    h2 = lambda e: None
    fresh_bus.subscribe(PaymentCaptured, h1)
    assert fresh_bus.handler_count(PaymentCaptured) == 1
    fresh_bus.subscribe(PaymentCaptured, h2)
    assert fresh_bus.handler_count(PaymentCaptured) == 2
    fresh_bus.unsubscribe(PaymentCaptured, h1)
    assert fresh_bus.handler_count(PaymentCaptured) == 1


# ── El singleton de módulo está correctamente expuesto ───────────────────────


def test_module_bus_is_the_real_eventbus_instance():
    assert isinstance(bus, _EventBus)
