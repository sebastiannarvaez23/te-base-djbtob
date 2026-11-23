"""
Tests del :class:`InvoiceBillingListener` — el puente Payments → Invoice.

Mockeamos el factory de :class:`DjangoInvoiceRepository` y el lookup
de :class:`CompanySubscription` para no requerir BD.
"""

import uuid
from datetime import date, datetime, timezone as tz
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from platform.features.billing.commerce.invoice.domain.schemas import (
    CreateInvoiceSchema,
    UpdateInvoiceStatusSchema,
)
from platform.features.billing.commerce.payments.domain.enums import GatewayProvider, MethodType
from platform.features.billing.commerce.payments.domain.events import (
    PaymentCanceled,
    PaymentCaptured,
    PaymentFailed,
    PaymentRefunded,
)
from platform.features.billing.commerce.payments.integration.invoice_billing import (
    InvoiceBillingListener,
    _generate_invoice_number,
)


pytestmark = pytest.mark.unit


# ── Helpers ──────────────────────────────────────────────────────────────────


def _captured(invoice_id=None, **overrides) -> PaymentCaptured:
    defaults = dict(
        charge_id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        gateway_provider=GatewayProvider.SIMULATOR,
        occurred_at=datetime.now(tz.utc),
        amount=Decimal('150000'),
        currency='COP',
        method_type=MethodType.CARD,
        invoice_id=invoice_id,
    )
    defaults.update(overrides)
    return PaymentCaptured(**defaults)


def _failed(invoice_id=None, **overrides) -> PaymentFailed:
    defaults = dict(
        charge_id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        gateway_provider=GatewayProvider.SIMULATOR,
        occurred_at=datetime.now(tz.utc),
        amount=Decimal('100'),
        currency='COP',
        method_type=MethodType.CARD,
        failure_code='card_declined',
        failure_message='nope',
        invoice_id=invoice_id,
    )
    defaults.update(overrides)
    return PaymentFailed(**defaults)


def _canceled(invoice_id=None, **overrides) -> PaymentCanceled:
    defaults = dict(
        charge_id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        gateway_provider=GatewayProvider.SIMULATOR,
        occurred_at=datetime.now(tz.utc),
        invoice_id=invoice_id,
    )
    defaults.update(overrides)
    return PaymentCanceled(**defaults)


def _refunded(invoice_id=None, is_partial=False, **overrides) -> PaymentRefunded:
    defaults = dict(
        charge_id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        gateway_provider=GatewayProvider.SIMULATOR,
        occurred_at=datetime.now(tz.utc),
        refund_amount=Decimal('100'),
        total_refunded=Decimal('100'),
        is_partial=is_partial,
        invoice_id=invoice_id,
    )
    defaults.update(overrides)
    return PaymentRefunded(**defaults)


def _make_listener(repo=None, subscription=None):
    """Listener con dependencias mockeadas. El publisher mock queda en
    ``listener._publish`` para inspeccionar los ``InvoiceIssued`` emitidos."""
    repo = repo if repo is not None else MagicMock()
    repo_factory = MagicMock(return_value=repo)
    lookup = MagicMock(return_value=subscription)
    listener = InvoiceBillingListener(
        invoice_repo_factory=repo_factory,
        subscription_lookup=lookup,
        publisher=MagicMock(),
    )
    return listener, repo, lookup


def _issued_events(listener):
    """Los InvoiceIssued publicados por el listener."""
    from platform.features.billing.commerce.payments.integration.events import InvoiceIssued
    return [c.args[0] for c in listener._publish.call_args_list
            if isinstance(c.args[0], InvoiceIssued)]


def _invoice_row(**overrides):
    """Stub mínimo de InvoiceSchema (lo que UpdateInvoiceStatusUseCase devuelve)."""
    from platform.features.billing.commerce.invoice.domain.schemas import InvoiceSchema
    defaults = dict(
        id=uuid.uuid4(),
        invoice_number='INV-001',
        company_id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
        issue_date=date.today(),
        due_date=date.today(),
        total_amount=Decimal('100'),
        currency='COP',
        status='paid',
        notes='',
    )
    defaults.update(overrides)
    return InvoiceSchema(**defaults)


# ── on_payment_captured: con invoice_id existente ────────────────────────────


def test_captured_with_invoice_id_marks_existing_invoice_as_paid():
    invoice_id = uuid.uuid4()
    repo = MagicMock()
    repo.get_by_id.return_value = _invoice_row(id=invoice_id, currency='COP')
    repo.update_status.return_value = _invoice_row(id=invoice_id, status='paid', currency='COP')
    listener, _, lookup = _make_listener(repo=repo)

    listener.on_payment_captured(_captured(invoice_id=invoice_id, currency='COP'))

    repo.update_status.assert_called_once()
    args = repo.update_status.call_args.args
    assert args[0] == invoice_id
    assert isinstance(args[1], UpdateInvoiceStatusSchema)
    assert args[1].status == 'paid'
    # No se generó invoice nueva.
    repo.create.assert_not_called()
    lookup.assert_not_called()


def test_captured_raises_on_currency_drift():
    from core.errors import ConflictException

    invoice_id = uuid.uuid4()
    repo = MagicMock()
    repo.get_by_id.return_value = _invoice_row(id=invoice_id, currency='USD')
    listener, _, _ = _make_listener(repo=repo)

    with pytest.raises(ConflictException):
        listener.on_payment_captured(_captured(invoice_id=invoice_id, currency='COP'))

    repo.update_status.assert_not_called()


def test_captured_with_invoice_id_logs_warning_when_invoice_missing(caplog):
    repo = MagicMock()
    repo.update_status.return_value = None  # invoice no existe
    listener, _, _ = _make_listener(repo=repo)

    import logging
    with caplog.at_level(logging.WARNING, logger='payments.integration.invoice'):
        listener.on_payment_captured(_captured(invoice_id=uuid.uuid4()))

    assert any('not found' in r.message for r in caplog.records)


def test_captured_with_invoice_id_swallows_repo_exception(caplog):
    """Errores al actualizar la invoice nunca deben romper el pago."""
    repo = MagicMock()
    repo.update_status.side_effect = RuntimeError('db down')
    listener, _, _ = _make_listener(repo=repo)

    import logging
    with caplog.at_level(logging.ERROR, logger='payments.integration.invoice'):
        listener.on_payment_captured(_captured(invoice_id=uuid.uuid4()))  # no raises

    assert any('failed to update invoice' in r.message for r in caplog.records)


# ── on_payment_captured: sin invoice_id → auto-genera ────────────────────────


def test_captured_without_invoice_id_creates_invoice_in_paid_state():
    company_id = uuid.uuid4()
    subscription_id = uuid.uuid4()
    company_sub = SimpleNamespace(
        id=uuid.uuid4(),
        company_id=company_id,
        subscription_id=subscription_id,
        start_date=datetime.now(tz.utc),
        status='active',
    )
    repo = MagicMock()
    repo.create.return_value = _invoice_row(company_id=company_id, subscription_id=subscription_id)
    listener, _, lookup = _make_listener(repo=repo, subscription=company_sub)

    event = _captured(invoice_id=None, company_id=company_id, amount=Decimal('250000'))
    listener.on_payment_captured(event)

    lookup.assert_called_once_with(company_id)
    repo.create.assert_called_once()
    schema: CreateInvoiceSchema = repo.create.call_args.args[0]
    assert isinstance(schema, CreateInvoiceSchema)
    assert schema.company_id == company_id
    assert schema.subscription_id == subscription_id
    assert schema.company_subscription_id == company_sub.id
    assert schema.source_charge_id == event.charge_id
    assert schema.metadata['source_charge_id'] == str(event.charge_id)
    assert schema.total_amount == Decimal('250000')
    assert schema.status == 'paid'
    assert schema.currency == 'COP'
    assert str(event.charge_id) in schema.notes


def test_auto_create_persists_promotion_snapshot():
    company_id = uuid.uuid4()
    company_sub = SimpleNamespace(
        subscription_id=uuid.uuid4(), start_date=datetime.now(tz.utc),
    )
    repo = MagicMock()
    repo.create.return_value = _invoice_row()
    listener, _, _ = _make_listener(repo=repo, subscription=company_sub)

    listener.on_payment_captured(_captured(
        invoice_id=None,
        company_id=company_id,
        amount=Decimal('80'),
        currency='USD',
        metadata={
            'promotion_serial': 'WLGX-DSC-1',
            'voucher_type': 'DISCOUNT',
            'original_amount': '100.00',
            'discount_amount': '20.00',
            'email_context': {
                'promotion_serial': 'WLGX-DSC-1',
                'promotion_voucher_type': 'DISCOUNT',
            },
        },
    ))

    schema: CreateInvoiceSchema = repo.create.call_args.args[0]
    assert schema.currency == 'USD'
    assert schema.metadata['promotion_serial'] == 'WLGX-DSC-1'
    assert schema.metadata['original_amount'] == '100.00'
    assert schema.metadata['promotion_voucher_type'] == 'DISCOUNT'


def test_zero_amount_charge_skips_invoice():
    repo = MagicMock()
    listener, _, _ = _make_listener(repo=repo, subscription=SimpleNamespace(
        subscription_id=uuid.uuid4(), start_date=datetime.now(tz.utc),
    ))
    listener.on_payment_captured(_captured(invoice_id=None, amount=Decimal('0')))
    repo.create.assert_not_called()
    assert _issued_events(listener) == []


def test_auto_created_invoice_announces_invoice_issued():
    """The auto-create branch publishes InvoiceIssued (with the new invoice id)
    so the delivery listener can email it — WITHOUT mutating the payment event."""
    company_id = uuid.uuid4()
    new_invoice_id = uuid.uuid4()
    company_sub = SimpleNamespace(
        subscription_id=uuid.uuid4(), start_date=datetime.now(tz.utc),
    )
    repo = MagicMock()
    repo.create.return_value = _invoice_row(id=new_invoice_id)
    listener, _, _ = _make_listener(repo=repo, subscription=company_sub)

    event = _captured(invoice_id=None, company_id=company_id)
    listener.on_payment_captured(event)

    issued = _issued_events(listener)
    assert len(issued) == 1
    assert issued[0].invoice_id == new_invoice_id
    assert issued[0].company_id == company_id
    # The payment event itself is NOT mutated.
    assert event.invoice_id is None


def test_no_invoice_issued_when_auto_create_fails():
    """No active subscription → no invoice → nothing announced."""
    listener, _, _ = _make_listener(repo=MagicMock(), subscription=None)

    event = _captured(invoice_id=None)
    listener.on_payment_captured(event)

    assert _issued_events(listener) == []


def test_existing_invoice_also_announces_invoice_issued():
    """Upfront-invoice path marks paid AND announces InvoiceIssued so delivery
    fires for that case too."""
    invoice_id = uuid.uuid4()
    repo = MagicMock()
    repo.update_status.return_value = _invoice_row(id=invoice_id, status='paid')
    listener, _, _ = _make_listener(repo=repo)

    listener.on_payment_captured(_captured(invoice_id=invoice_id))

    issued = _issued_events(listener)
    assert len(issued) == 1
    assert issued[0].invoice_id == invoice_id


def test_invoice_issued_carries_email_routing_from_metadata():
    """The email-template hint travels from the charge metadata onto
    InvoiceIssued (so routing lives on a billing event, not the payment one)."""
    invoice_id = uuid.uuid4()
    repo = MagicMock()
    repo.update_status.return_value = _invoice_row(id=invoice_id)
    listener, _, _ = _make_listener(repo=repo)

    listener.on_payment_captured(_captured(
        invoice_id=invoice_id,
        metadata={'email_template_code': 'SUB_UPGRADE', 'email_context': {'new_plan': 'Pro'}},
    ))

    issued = _issued_events(listener)[0]
    assert issued.email_template_code == 'SUB_UPGRADE'
    assert issued.email_context == {'new_plan': 'Pro'}


def test_auto_generated_invoice_number_has_expected_format():
    company_sub = SimpleNamespace(subscription_id=uuid.uuid4(), start_date=datetime.now(tz.utc))
    repo = MagicMock()
    repo.create.return_value = _invoice_row()
    listener, _, _ = _make_listener(repo=repo, subscription=company_sub)

    listener.on_payment_captured(_captured(invoice_id=None))

    schema = repo.create.call_args.args[0]
    # Patrón: INV-YYYYMM-XXXXXXXX
    parts = schema.invoice_number.split('-')
    assert len(parts) == 3
    assert parts[0] == 'INV'
    assert len(parts[1]) == 6 and parts[1].isdigit()
    assert len(parts[2]) == 8


def test_generated_invoice_numbers_are_unique():
    """100 generaciones consecutivas deben dar 100 números distintos."""
    numbers = {_generate_invoice_number() for _ in range(100)}
    assert len(numbers) == 100


def test_captured_without_invoice_id_skips_when_no_active_subscription(caplog):
    repo = MagicMock()
    listener, _, lookup = _make_listener(repo=repo, subscription=None)

    import logging
    with caplog.at_level(logging.WARNING, logger='payments.integration.invoice'):
        listener.on_payment_captured(_captured(invoice_id=None))

    lookup.assert_called_once()
    repo.create.assert_not_called()
    assert any('no active subscription' in r.message for r in caplog.records)


def test_captured_without_invoice_id_swallows_create_exception(caplog):
    company_sub = SimpleNamespace(subscription_id=uuid.uuid4(), start_date=datetime.now(tz.utc))
    repo = MagicMock()
    repo.create.side_effect = RuntimeError('insert failed')
    listener, _, _ = _make_listener(repo=repo, subscription=company_sub)

    import logging
    with caplog.at_level(logging.ERROR, logger='payments.integration.invoice'):
        listener.on_payment_captured(_captured(invoice_id=None))

    assert any('failed to auto-generate invoice' in r.message for r in caplog.records)


# ── on_payment_failed ────────────────────────────────────────────────────────


def test_failed_with_invoice_id_marks_overdue():
    invoice_id = uuid.uuid4()
    repo = MagicMock()
    repo.update_status.return_value = _invoice_row(id=invoice_id, status='overdue')
    listener, _, _ = _make_listener(repo=repo)

    listener.on_payment_failed(_failed(invoice_id=invoice_id))

    repo.update_status.assert_called_once()
    assert repo.update_status.call_args.args[1].status == 'overdue'


def test_failed_without_invoice_id_is_noop():
    repo = MagicMock()
    listener, _, lookup = _make_listener(repo=repo)

    listener.on_payment_failed(_failed(invoice_id=None))

    repo.update_status.assert_not_called()
    repo.create.assert_not_called()
    lookup.assert_not_called()


# ── on_payment_canceled ──────────────────────────────────────────────────────


def test_canceled_with_invoice_id_marks_cancelled():
    invoice_id = uuid.uuid4()
    repo = MagicMock()
    repo.update_status.return_value = _invoice_row(id=invoice_id, status='cancelled')
    listener, _, _ = _make_listener(repo=repo)

    listener.on_payment_canceled(_canceled(invoice_id=invoice_id))

    assert repo.update_status.call_args.args[1].status == 'cancelled'


def test_canceled_without_invoice_id_is_noop():
    repo = MagicMock()
    listener, _, _ = _make_listener(repo=repo)
    listener.on_payment_canceled(_canceled(invoice_id=None))
    repo.update_status.assert_not_called()


# ── on_payment_refunded ──────────────────────────────────────────────────────


def test_full_refund_with_invoice_id_marks_cancelled():
    invoice_id = uuid.uuid4()
    repo = MagicMock()
    repo.update_status.return_value = _invoice_row(id=invoice_id, status='cancelled')
    listener, _, _ = _make_listener(repo=repo)

    listener.on_payment_refunded(_refunded(invoice_id=invoice_id, is_partial=False))

    assert repo.update_status.call_args.args[1].status == 'cancelled'


def test_partial_refund_does_not_touch_invoice():
    repo = MagicMock()
    listener, _, _ = _make_listener(repo=repo)

    listener.on_payment_refunded(_refunded(invoice_id=uuid.uuid4(), is_partial=True))

    repo.update_status.assert_not_called()


def test_refund_without_invoice_id_is_noop():
    repo = MagicMock()
    listener, _, _ = _make_listener(repo=repo)
    listener.on_payment_refunded(_refunded(invoice_id=None, is_partial=False))
    repo.update_status.assert_not_called()


# ── Wireup desde apps.py ─────────────────────────────────────────────────────


def test_apps_ready_subscribes_one_handler_per_event():
    """Confirma que el AppConfig registró 1 handler por evento de interés."""
    from platform.features.billing.commerce.payments.domain.events import (
        bus, PaymentCaptured, PaymentFailed, PaymentCanceled, PaymentRefunded,
    )
    # No menor que 1; podría ser >1 si otros tests dejaron suscripciones.
    assert bus.handler_count(PaymentCaptured) >= 1
    assert bus.handler_count(PaymentFailed) >= 1
    assert bus.handler_count(PaymentCanceled) >= 1
    assert bus.handler_count(PaymentRefunded) >= 1


def test_apps_ready_subscribes_delivery_to_invoice_issued():
    """Delivery escucha InvoiceIssued (no PaymentCaptured): el wiring de apps.py
    debe haber registrado el handler del evento de billing."""
    from platform.features.billing.commerce.payments.domain.events import bus
    from platform.features.billing.commerce.payments.integration.events import InvoiceIssued
    assert bus.handler_count(InvoiceIssued) >= 1
