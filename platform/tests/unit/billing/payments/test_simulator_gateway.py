"""
Tests del :class:`SimulatedGateway`.

Cubre cada verbo del puerto y cada escenario de ``Scenario``. Es un
gateway in-process — no requiere red, mocks ni BD.

Cada test resetea el estado compartido del simulator vía la fixture
``clean_simulator`` para evitar fugas entre tests (la clase mantiene un
diccionario de clase).
"""

import json
import uuid
from decimal import Decimal

import pytest

from platform.features.billing.commerce.payments.domain.enums import (
    ChargeStatus,
    GatewayProvider,
    MethodType,
    NextActionType,
    WebhookEventType,
)
from platform.features.billing.commerce.payments.domain.schemas import (
    CardData,
    ChargeRequest,
    PayerRef,
    RefundRequest,
)
from platform.features.billing.commerce.payments.infrastructure.gateways.simulator.gateway import (
    SIMULATOR_WEBHOOK_SECRET,
    SimulatedGateway,
)


pytestmark = pytest.mark.unit


@pytest.fixture
def clean_simulator():
    """Resetea el estado compartido entre tests."""
    SimulatedGateway._store.clear()
    SimulatedGateway._idempotency.clear()
    yield
    SimulatedGateway._store.clear()
    SimulatedGateway._idempotency.clear()


@pytest.fixture
def gateway(clean_simulator):
    return SimulatedGateway()


def _request(**overrides) -> ChargeRequest:
    defaults = dict(
        payer=PayerRef(company_id=uuid.uuid4()),
        amount=Decimal('15000'),
        currency='COP',
        method_type=MethodType.CARD,
        card=CardData(number='4242424242424242', exp_month=12, exp_year=2030, cvc='123'),
    )
    defaults.update(overrides)
    return ChargeRequest(**defaults)


# ── Identidad del adapter ─────────────────────────────────────────────────────


def test_provider_identifier_is_simulator(gateway):
    assert gateway.provider == GatewayProvider.SIMULATOR


# ── create_charge: cada escenario ─────────────────────────────────────────────


def test_succeed_scenario_returns_captured(gateway):
    result = gateway.create_charge(_request(), idempotency_key='k1')
    assert result.status == ChargeStatus.CAPTURED
    assert result.gateway_charge_id.startswith('sim_ch_')
    assert result.failure_code == ''
    assert result.next_action is None


def test_decline_scenario_returns_failed_with_failure_code(gateway):
    request = _request(card=CardData(number='4000000000000002'))
    result = gateway.create_charge(request, idempotency_key='k1')
    assert result.status == ChargeStatus.FAILED
    assert result.failure_code == 'card_declined'
    assert 'rechaz' in result.failure_message.lower()


def test_insufficient_funds_returns_failed(gateway):
    request = _request(card=CardData(number='4000000000009995'))
    result = gateway.create_charge(request, idempotency_key='k1')
    assert result.status == ChargeStatus.FAILED
    assert result.failure_code == 'insufficient_funds'


def test_expired_card_returns_failed(gateway):
    request = _request(card=CardData(number='4000000000000069'))
    result = gateway.create_charge(request, idempotency_key='k1')
    assert result.status == ChargeStatus.FAILED
    assert result.failure_code == 'expired_card'


def test_processor_error_returns_failed(gateway):
    request = _request(card=CardData(number='4000000000000119'))
    result = gateway.create_charge(request, idempotency_key='k1')
    assert result.status == ChargeStatus.FAILED
    assert result.failure_code == 'processor_error'


def test_requires_action_returns_redirect_next_action(gateway):
    request = _request(
        card=CardData(number='4000000000003220'),
        return_url='https://example.com/return',
    )
    result = gateway.create_charge(request, idempotency_key='k1')
    assert result.status == ChargeStatus.REQUIRES_ACTION
    assert result.next_action is not None
    assert result.next_action.type == NextActionType.REDIRECT
    assert result.next_action.url == 'https://example.com/return'


def test_authorize_only_returns_authorized_without_capture(gateway):
    request = _request(card=CardData(number='4111111111111111'))
    result = gateway.create_charge(request, idempotency_key='k1')
    assert result.status == ChargeStatus.AUTHORIZED


def test_async_pending_for_pse_returns_processing_with_await_webhook(gateway):
    request = _request(method_type=MethodType.PSE, card=None)
    result = gateway.create_charge(request, idempotency_key='k1')
    assert result.status == ChargeStatus.PROCESSING
    assert result.next_action is not None
    assert result.next_action.type == NextActionType.AWAIT_WEBHOOK
    assert result.next_action.voucher_reference.startswith('sim_vch_')


def test_async_pending_for_voucher(gateway):
    request = _request(method_type=MethodType.VOUCHER, card=None)
    result = gateway.create_charge(request, idempotency_key='k1')
    assert result.status == ChargeStatus.PROCESSING


# ── Idempotency ───────────────────────────────────────────────────────────────


def test_same_idempotency_key_returns_same_response(gateway):
    request1 = _request(amount=Decimal('100'))
    request2 = _request(amount=Decimal('999999'), description='changed')

    r1 = gateway.create_charge(request1, idempotency_key='same-key')
    r2 = gateway.create_charge(request2, idempotency_key='same-key')

    assert r1.gateway_charge_id == r2.gateway_charge_id
    assert r1.amount == r2.amount == Decimal('100')  # se preserva el monto original


def test_different_idempotency_keys_create_distinct_charges(gateway):
    r1 = gateway.create_charge(_request(), idempotency_key='k1')
    r2 = gateway.create_charge(_request(), idempotency_key='k2')
    assert r1.gateway_charge_id != r2.gateway_charge_id


def test_empty_idempotency_key_does_not_cache(gateway):
    r1 = gateway.create_charge(_request(), idempotency_key='')
    r2 = gateway.create_charge(_request(), idempotency_key='')
    assert r1.gateway_charge_id != r2.gateway_charge_id


# ── confirm_charge ────────────────────────────────────────────────────────────


def test_confirm_moves_requires_action_to_captured(gateway):
    request = _request(card=CardData(number='4000000000003220'))
    initial = gateway.create_charge(request, idempotency_key='k1')
    assert initial.status == ChargeStatus.REQUIRES_ACTION

    confirmed = gateway.confirm_charge(initial.gateway_charge_id)
    assert confirmed.status == ChargeStatus.CAPTURED
    assert confirmed.next_action is None


def test_confirm_moves_processing_to_captured(gateway):
    """PSE en processing → confirm lo lleva a captured (simula el webhook)."""
    initial = gateway.create_charge(_request(method_type=MethodType.PSE, card=None), idempotency_key='k1')
    assert initial.status == ChargeStatus.PROCESSING

    confirmed = gateway.confirm_charge(initial.gateway_charge_id)
    assert confirmed.status == ChargeStatus.CAPTURED


def test_confirm_unknown_charge_raises(gateway):
    with pytest.raises(LookupError):
        gateway.confirm_charge('does-not-exist')


# ── capture_charge ────────────────────────────────────────────────────────────


def test_capture_moves_authorized_to_captured(gateway):
    request = _request(card=CardData(number='4111111111111111'))
    initial = gateway.create_charge(request, idempotency_key='k1')
    assert initial.status == ChargeStatus.AUTHORIZED

    captured = gateway.capture_charge(initial.gateway_charge_id)
    assert captured.status == ChargeStatus.CAPTURED


def test_capture_on_already_captured_is_idempotent(gateway):
    initial = gateway.create_charge(_request(), idempotency_key='k1')
    again = gateway.capture_charge(initial.gateway_charge_id)
    assert again.status == ChargeStatus.CAPTURED


# ── cancel_charge ─────────────────────────────────────────────────────────────


def test_cancel_on_authorized_moves_to_canceled(gateway):
    request = _request(card=CardData(number='4111111111111111'))
    initial = gateway.create_charge(request, idempotency_key='k1')
    canceled = gateway.cancel_charge(initial.gateway_charge_id, reason='changed mind')
    assert canceled.status == ChargeStatus.CANCELED


def test_cancel_on_requires_action_moves_to_canceled(gateway):
    request = _request(card=CardData(number='4000000000003220'))
    initial = gateway.create_charge(request, idempotency_key='k1')
    canceled = gateway.cancel_charge(initial.gateway_charge_id)
    assert canceled.status == ChargeStatus.CANCELED


def test_cancel_on_captured_does_not_change_state(gateway):
    """Un captured no se puede cancelar — el simulator devuelve el estado tal cual."""
    initial = gateway.create_charge(_request(), idempotency_key='k1')
    assert initial.status == ChargeStatus.CAPTURED
    result = gateway.cancel_charge(initial.gateway_charge_id)
    assert result.status == ChargeStatus.CAPTURED


# ── refund_charge ─────────────────────────────────────────────────────────────


def test_full_refund_when_amount_is_none(gateway):
    initial = gateway.create_charge(_request(amount=Decimal('100')), idempotency_key='k1')
    refund = gateway.refund_charge(RefundRequest(
        gateway_charge_id=initial.gateway_charge_id,
    ))
    assert refund.amount == Decimal('100')
    assert refund.status == ChargeStatus.REFUNDED
    assert refund.gateway_refund_id.startswith('sim_rf_')


def test_partial_refund_moves_to_partially_refunded(gateway):
    initial = gateway.create_charge(_request(amount=Decimal('100')), idempotency_key='k1')
    refund = gateway.refund_charge(RefundRequest(
        gateway_charge_id=initial.gateway_charge_id,
        amount=Decimal('40'),
    ))
    assert refund.amount == Decimal('40')
    assert refund.status == ChargeStatus.PARTIALLY_REFUNDED


def test_two_partial_refunds_summing_total_lead_to_fully_refunded(gateway):
    initial = gateway.create_charge(_request(amount=Decimal('100')), idempotency_key='k1')
    first = gateway.refund_charge(RefundRequest(
        gateway_charge_id=initial.gateway_charge_id, amount=Decimal('30'),
    ))
    assert first.status == ChargeStatus.PARTIALLY_REFUNDED
    second = gateway.refund_charge(RefundRequest(
        gateway_charge_id=initial.gateway_charge_id, amount=Decimal('70'),
    ))
    assert second.status == ChargeStatus.REFUNDED


def test_refund_when_nothing_left_returns_zero(gateway):
    initial = gateway.create_charge(_request(amount=Decimal('100')), idempotency_key='k1')
    gateway.refund_charge(RefundRequest(gateway_charge_id=initial.gateway_charge_id))
    # Ya está totalmente reembolsado; otra llamada con amount=None.
    second = gateway.refund_charge(RefundRequest(gateway_charge_id=initial.gateway_charge_id))
    assert second.amount == Decimal('0')


def test_refund_unknown_charge_raises(gateway):
    with pytest.raises(LookupError):
        gateway.refund_charge(RefundRequest(gateway_charge_id='nope'))


# ── fetch_charge ──────────────────────────────────────────────────────────────


def test_fetch_returns_current_state(gateway):
    initial = gateway.create_charge(_request(), idempotency_key='k1')
    fetched = gateway.fetch_charge(initial.gateway_charge_id)
    assert fetched.status == initial.status
    assert fetched.gateway_charge_id == initial.gateway_charge_id


def test_fetch_unknown_charge_raises(gateway):
    with pytest.raises(LookupError):
        gateway.fetch_charge('nope')


# ── webhooks ──────────────────────────────────────────────────────────────────


def test_webhook_signature_with_valid_hmac_is_accepted(gateway):
    import hmac
    import hashlib
    payload = b'{"type":"charge.captured","id":"evt_1"}'
    expected = hmac.new(SIMULATOR_WEBHOOK_SECRET, payload, hashlib.sha256).hexdigest()
    assert gateway.verify_webhook_signature(payload, expected) is True


def test_webhook_signature_with_wrong_value_is_rejected(gateway):
    payload = b'{"type":"charge.captured"}'
    assert gateway.verify_webhook_signature(payload, 'definitely-not-right') is False


def test_webhook_signature_with_empty_header_is_rejected(gateway):
    assert gateway.verify_webhook_signature(b'{}', '') is False


def test_parse_webhook_event_returns_normalized_event(gateway):
    payload = json.dumps({
        'id': 'evt_123',
        'type': WebhookEventType.CHARGE_CAPTURED.value,
        'charge_id': 'sim_ch_abc',
        'status': ChargeStatus.CAPTURED.value,
        'amount': '150.00',
        'currency': 'COP',
    }).encode('utf-8')
    event = gateway.parse_webhook_event(payload)
    assert event.provider == GatewayProvider.SIMULATOR
    assert event.external_event_id == 'evt_123'
    assert event.event_type == WebhookEventType.CHARGE_CAPTURED
    assert event.gateway_charge_id == 'sim_ch_abc'
    assert event.status == ChargeStatus.CAPTURED
    assert event.amount == Decimal('150.00')
    assert event.currency == 'COP'


# ── Thread safety (estado compartido entre instancias) ────────────────────────


def test_state_is_shared_between_gateway_instances(clean_simulator):
    """Dos instancias del simulator ven el mismo store (es estado de clase)."""
    g1 = SimulatedGateway()
    g2 = SimulatedGateway()
    created = g1.create_charge(_request(), idempotency_key='k1')
    seen = g2.fetch_charge(created.gateway_charge_id)
    assert seen.gateway_charge_id == created.gateway_charge_id
