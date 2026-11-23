"""Unit tests for public purchase email contexts."""

import uuid
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from platform.features.billing.commerce.promotion.application.voucher_emails import (
    build_recipient_discount_email_context,
    build_recipient_gift_email_context,
    build_voucher_purchased_email_context,
    dispatch_public_purchase_emails,
)
from platform.features.billing.commerce.promotion.models import PromotionVoucher

pytestmark = pytest.mark.unit


def _voucher(**kwargs):
    defaults = dict(
        serial='WLGX-GFT-TEST01',
        voucher_type=PromotionVoucher.VoucherType.GIFT,
        benefit_months=3,
        discount_percent=None,
        discount_duration_months=1,
        redeem_valid_until=datetime(2026, 12, 31, 23, 59, 59),
        notes='',
        company_id=None,
        company=None,
        subscriptions=MagicMock(),
    )
    defaults.update(kwargs)
    voucher = SimpleNamespace(**defaults)
    sub = SimpleNamespace(id=uuid.uuid4(), name='Profesional', code='pro', price=Decimal('129.00'))
    names_qs = MagicMock()
    names_qs.first.return_value = 'Profesional'
    names_qs.__iter__ = lambda self: iter(['Profesional'])
    voucher.subscriptions.first.return_value = sub
    voucher.subscriptions.values_list.return_value = names_qs
    return voucher


def test_build_recipient_gift_email_context():
    buyer = SimpleNamespace(name='María González', email='buyer@test.com')
    recipient = SimpleNamespace(
        name='Carlos Rodríguez',
        email='recipient@test.com',
        message='Feliz año',
        company_name='Tecnologías Andinas S.A.S.',
    )

    ctx = build_recipient_gift_email_context(
        voucher=_voucher(),
        buyer=buyer,
        recipient=recipient,
        amount_paid=Decimal('600000'),
        currency='COP',
    )

    assert ctx['recipient_name'] == 'Carlos Rodríguez'
    assert ctx['sender_name'] == 'María González'
    assert ctx['voucher_code'] == 'WLGX-GFT-TEST01'
    assert ctx['gift_value'] == '$600.000 COP'
    assert ctx['usage_limit'] == '1 uso'
    assert ctx['subscription_name'] == 'Profesional'
    assert ctx['subscription_duration'] == '3 meses'
    assert ctx['expiration_date'] == '31/12/2026'
    assert '/redeem/WLGX-GFT-TEST01' in ctx['redeem_url']


def test_build_recipient_discount_email_context():
    buyer = SimpleNamespace(name='Carlos Rodríguez', email='buyer@test.com')
    recipient = SimpleNamespace(
        name='Laura Gómez',
        email='laura@test.com',
        message='',
        company_name='Logística Andina S.A.S.',
    )

    ctx = build_recipient_discount_email_context(
        voucher=_voucher(
            serial='WLGX-DSC-TEST01',
            voucher_type=PromotionVoucher.VoucherType.DISCOUNT,
            discount_percent=Decimal('25'),
            discount_duration_months=3,
        ),
        buyer=buyer,
        recipient=recipient,
        currency='USD',
    )

    assert ctx['discount'] == '25%'
    assert ctx['discount_type'] == 'Porcentaje'
    assert ctx['usage_limit'] == '1 uso'
    assert ctx['voucher_code'] == 'WLGX-DSC-TEST01'
    assert 'Profesional' in ctx['subscriptions']
    assert ctx['expiration_date'] == '31/12/2026'
    assert ctx['discount_conditions']


def test_build_voucher_purchased_email_context():
    buyer = SimpleNamespace(name='Carlos Rodríguez', email='buyer@test.com')
    recipient = SimpleNamespace(
        name='Laura Gómez',
        email='laura@test.com',
        message='',
        company_name='Logística Andina S.A.S.',
    )

    ctx = build_voucher_purchased_email_context(
        voucher=_voucher(),
        buyer=buyer,
        recipient=recipient,
        amount_paid=Decimal('100000'),
        order_number='ORD-20260709-000158',
        currency='COP',
    )

    assert ctx['buyer_name'] == 'Carlos Rodríguez'
    assert ctx['order_number'] == 'ORD-20260709-000158'
    assert 'COP' in ctx['total_paid']
    assert ctx['recipient_email'] == 'laura@test.com'
    assert ctx['payment_status'] == 'Pagado'
    assert ctx['voucher_type'] == 'Bono Regalo'


@patch('platform.features.billing.commerce.promotion.application.voucher_emails.threading.Thread')
def test_dispatch_public_purchase_emails_uses_gift_voucher(mock_thread):
    buyer = SimpleNamespace(name='Buyer', email='buyer@test.com')
    recipient = SimpleNamespace(
        name='Recipient',
        email='recipient@test.com',
        message='Hola',
        company_name='Acme',
    )
    dispatch_public_purchase_emails(
        notifier=MagicMock(),
        voucher=_voucher(),
        buyer=buyer,
        recipient=recipient,
        amount_paid=Decimal('299'),
        currency='USD',
    )
    mock_thread.assert_called_once()
