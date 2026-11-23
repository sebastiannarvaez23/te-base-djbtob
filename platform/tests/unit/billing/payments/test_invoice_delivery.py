"""Tests del :class:`InvoiceDeliveryListener` — envía el PDF de la factura
al recibir ``InvoiceIssued`` (publicado por el billing listener).

El destinatario primario es el admin de la empresa (un único usuario por
empresa). Inyectamos ``admin_email_lookup`` para no tocar la BD, y parcheamos
:class:`SendInvoiceUseCase` para no renderizar PDF real ni tocar MinIO/SMTP.
"""
import uuid
from datetime import datetime, timezone as tz
from unittest.mock import MagicMock, patch

import pytest

from platform.features.billing.commerce.payments.integration.events import InvoiceIssued
from platform.features.billing.commerce.payments.integration.invoice_delivery import (
    InvoiceDeliveryListener,
)


pytestmark = pytest.mark.unit


def _issued(invoice_id=None, recipient_email=None, email_template_code=None,
            email_context=None, **overrides) -> InvoiceIssued:
    defaults = dict(
        invoice_id=invoice_id or uuid.uuid4(),
        company_id=uuid.uuid4(),
        charge_id=uuid.uuid4(),
        recipient_email=recipient_email,
        email_template_code=email_template_code,
        email_context=email_context,
    )
    defaults.update(overrides)
    return InvoiceIssued(**defaults)


def _listener(admin_email=None):
    """Listener con admin lookup inyectado (sin BD)."""
    return InvoiceDeliveryListener(
        invoice_repo_factory=MagicMock(),
        storage_factory=MagicMock(),
        template_loader_factory=MagicMock(),
        render_resolver_factory=MagicMock(),
        path_resolver_factory=MagicMock(),
        admin_email_lookup=MagicMock(return_value=admin_email),
    )


_PATCH_TARGET = (
    'platform.features.billing.commerce.payments.integration.invoice_delivery.SendInvoiceUseCase'
)


def test_delivers_to_company_admin():
    invoice_id = uuid.uuid4()
    listener = _listener(admin_email='admin@acme.com')
    event = _issued(invoice_id=invoice_id)

    with patch(_PATCH_TARGET) as MockUseCase:
        MockUseCase.return_value.execute.return_value = MagicMock(
            invoice_id=invoice_id, sent_to='admin@acme.com', object_key='k',
        )
        listener.on_invoice_issued(event)

    MockUseCase.return_value.execute.assert_called_once_with(invoice_id, 'admin@acme.com', email_context=None)


def test_admin_lookup_is_called_with_company_id():
    company_id = uuid.uuid4()
    lookup = MagicMock(return_value='admin@acme.com')
    listener = InvoiceDeliveryListener(
        invoice_repo_factory=MagicMock(),
        storage_factory=MagicMock(),
        template_loader_factory=MagicMock(),
        render_resolver_factory=MagicMock(),
        path_resolver_factory=MagicMock(),
        admin_email_lookup=lookup,
    )
    event = _issued(company_id=company_id)

    with patch(_PATCH_TARGET):
        listener.on_invoice_issued(event)

    lookup.assert_called_once_with(company_id)


def test_admin_wins_over_recipient_email():
    invoice_id = uuid.uuid4()
    listener = _listener(admin_email='admin@acme.com')
    event = _issued(invoice_id=invoice_id, recipient_email='other@x.com')

    with patch(_PATCH_TARGET) as MockUseCase:
        listener.on_invoice_issued(event)

    MockUseCase.return_value.execute.assert_called_once_with(invoice_id, 'admin@acme.com', email_context=None)


def test_falls_back_to_recipient_email_when_no_admin():
    invoice_id = uuid.uuid4()
    listener = _listener(admin_email=None)
    event = _issued(invoice_id=invoice_id, recipient_email='billing@x.com')

    with patch(_PATCH_TARGET) as MockUseCase:
        listener.on_invoice_issued(event)

    MockUseCase.return_value.execute.assert_called_once_with(invoice_id, 'billing@x.com', email_context=None)


def test_falls_back_to_setting_when_no_admin_no_recipient(settings):
    settings.INVOICE_FALLBACK_RECIPIENT = 'ops@base.local'
    invoice_id = uuid.uuid4()
    listener = _listener(admin_email=None)
    event = _issued(invoice_id=invoice_id)

    with patch(_PATCH_TARGET) as MockUseCase:
        listener.on_invoice_issued(event)

    MockUseCase.return_value.execute.assert_called_once_with(invoice_id, 'ops@base.local', email_context=None)


def test_skips_when_no_recipient_anywhere(settings):
    settings.INVOICE_FALLBACK_RECIPIENT = ''
    listener = _listener(admin_email=None)
    event = _issued()

    with patch(_PATCH_TARGET) as MockUseCase:
        listener.on_invoice_issued(event)

    MockUseCase.assert_not_called()


def test_routes_template_and_context_from_event():
    """The delivery routes the email template + context carried on the event
    (e.g. an upgrade's SUB_UPGRADE), not the default."""
    invoice_id = uuid.uuid4()
    listener = _listener(admin_email='admin@acme.com')
    ctx = {'new_plan': 'Pro', 'user_name': 'Ana'}
    event = _issued(invoice_id=invoice_id, email_template_code='SUB_UPGRADE', email_context=ctx)

    with patch(_PATCH_TARGET) as MockUseCase:
        listener.on_invoice_issued(event)

    assert MockUseCase.call_args.kwargs.get('email_template_code') == 'SUB_UPGRADE'
    MockUseCase.return_value.execute.assert_called_once_with(invoice_id, 'admin@acme.com', email_context=ctx)


def test_merges_promotion_fields_from_charge_metadata():
    """Promo amounts often live on charge metadata root; PDF needs them in email_context."""
    invoice_id = uuid.uuid4()
    listener = _listener(admin_email='admin@acme.com')
    event = _issued(
        invoice_id=invoice_id,
        email_context={'promotion_serial': 'WLGX-DSC-META01'},
        metadata={
            'promotion_serial': 'WLGX-DSC-META01',
            'voucher_type': 'DISCOUNT',
            'original_amount': '100.00',
            'discount_amount': '20.00',
            'email_context': {
                'promotion_serial': 'WLGX-DSC-META01',
                'promotion_voucher_type': 'DISCOUNT',
                'promotion_original_amount': 100.0,
                'promotion_discount_amount': 20.0,
            },
        },
    )

    with patch(_PATCH_TARGET) as MockUseCase:
        listener.on_invoice_issued(event)

    _, kwargs = MockUseCase.return_value.execute.call_args
    ctx = kwargs['email_context']
    assert ctx['promotion_serial'] == 'WLGX-DSC-META01'
    assert ctx['original_amount'] == '100.00'
    assert ctx['discount_amount'] == '20.00'
    assert ctx['voucher_type'] == 'DISCOUNT'


def test_use_case_exception_never_breaks_payment_flow():
    listener = _listener(admin_email='admin@acme.com')
    event = _issued()

    with patch(_PATCH_TARGET) as MockUseCase:
        MockUseCase.return_value.execute.side_effect = RuntimeError('render boom')
        listener.on_invoice_issued(event)  # must not raise


def test_chain_autocreated_invoice_is_delivered_to_admin():
    """End-to-end of the two listeners: billing auto-creates + publishes
    InvoiceIssued, delivery then emails the company admin. This is the
    subscription-payment → invoice path, now without event mutation."""
    from types import SimpleNamespace
    from decimal import Decimal
    from platform.features.billing.commerce.payments.domain.enums import GatewayProvider, MethodType
    from platform.features.billing.commerce.payments.domain.events import PaymentCaptured
    from platform.features.billing.commerce.payments.integration.invoice_billing import (
        InvoiceBillingListener,
    )

    new_invoice_id = uuid.uuid4()
    published = []
    billing_repo = MagicMock()
    billing_repo.create.return_value = SimpleNamespace(id=new_invoice_id)
    billing = InvoiceBillingListener(
        invoice_repo_factory=MagicMock(return_value=billing_repo),
        subscription_lookup=MagicMock(return_value=SimpleNamespace(
            subscription_id=uuid.uuid4(), start_date=datetime.now(tz.utc),
        )),
        publisher=published.append,
    )
    delivery = _listener(admin_email='admin@acme.com')

    captured = PaymentCaptured(
        charge_id=uuid.uuid4(), company_id=uuid.uuid4(),
        gateway_provider=GatewayProvider.SIMULATOR, occurred_at=datetime.now(tz.utc),
        amount=Decimal('150000'), currency='COP', method_type=MethodType.CARD,
        invoice_id=None,
    )

    with patch(_PATCH_TARGET) as MockUseCase:
        MockUseCase.return_value.execute.return_value = MagicMock(
            invoice_id=new_invoice_id, sent_to='admin@acme.com', object_key='k',
        )
        billing.on_payment_captured(captured)        # publishes InvoiceIssued
        assert len(published) == 1
        delivery.on_invoice_issued(published[0])     # delivers it

    MockUseCase.return_value.execute.assert_called_once_with(new_invoice_id, 'admin@acme.com', email_context=None)
