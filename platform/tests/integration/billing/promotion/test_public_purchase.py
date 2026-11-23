"""M — Public purchase integration tests (Fase 5)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from platform.features.billing.commerce.payment_method.models import PaymentMethod
from platform.features.billing.commerce.promotion.application.public_purchase import (
    PublicPurchaseCheckoutUseCase,
    PublicPurchasePreviewUseCase,
)
from platform.features.billing.commerce.promotion.domain.schemas import (
    PublicPurchaseBuyerSchema,
    PublicPurchaseCheckoutSchema,
    PublicPurchasePaymentSchema,
    PublicPurchasePreviewRequestSchema,
    PublicPurchaseRecipientSchema,
)
from platform.features.billing.commerce.promotion.models import PromotionVoucher

pytestmark = pytest.mark.integration

_CATALOG = {
    'gift': [{'subscription_code': 'PRO', 'benefit_months': 3, 'price': 299}],
    'discount': [{
        'subscription_code': 'PRO',
        'discount_percent': 20,
        'discount_duration_months': 3,
        'price': 149,
    }],
}


@pytest.fixture
def plan_pro_catalog(db):
    from platform.features.billing.subscription.subscription.models import Subscription

    return Subscription.objects.create(
        name='Profesional',
        code='PRO',
        price=Decimal('99.00'),
        is_active=True,
    )


def _buyer():
    return PublicPurchaseBuyerSchema(
        name='Jane Buyer',
        email='buyer@example.com',
        phone='3001234567',
        country='Colombia',
    )


def _recipient():
    return PublicPurchaseRecipientSchema(
        name='John Recipient',
        email='recipient@example.com',
        message='Feliz año',
        company_name='Acme',
    )


def _payment(card_number='4242424242424242'):
    return PublicPurchasePaymentSchema(
        processor_token=f'dev-token-{uuid.uuid4().hex[:8]}',
        holder='JANE BUYER',
        last4='4242',
        expiry_month=12,
        expiry_year=2030,
        card_number=card_number,
    )


@override_settings(PROMO_GIFT_CATALOG_JSON=_CATALOG)
def test_m1_preview_gift_catalog_price(plan_pro_catalog, company_a):
    with override_settings(PROMO_PUBLIC_BILLING_COMPANY_ID=str(company_a.id)):
        result = PublicPurchasePreviewUseCase().execute(
            PublicPurchasePreviewRequestSchema(
                voucher_type='GIFT',
                subscription_id=plan_pro_catalog.id,
                benefit_months=3,
            )
        )
    assert result.amount == Decimal('299')
    assert 'Profesional' in result.description


@override_settings(PROMO_GIFT_CATALOG_JSON=_CATALOG)
def test_m2_preview_discount_catalog_price(plan_pro_catalog, company_a):
    with override_settings(PROMO_PUBLIC_BILLING_COMPANY_ID=str(company_a.id)):
        result = PublicPurchasePreviewUseCase().execute(
            PublicPurchasePreviewRequestSchema(
                voucher_type='DISCOUNT',
                subscription_id=plan_pro_catalog.id,
                discount_percent=Decimal('20'),
                discount_duration_months=3,
            )
        )
    assert result.amount == Decimal('59.40')


@override_settings(PROMO_GIFT_CATALOG_JSON=_CATALOG)
def test_m3_checkout_gift_creates_open_voucher(plan_pro_catalog, company_a):
    with override_settings(PROMO_PUBLIC_BILLING_COMPANY_ID=str(company_a.id)):
        result = PublicPurchaseCheckoutUseCase().execute(
            PublicPurchaseCheckoutSchema(
                voucher_type='GIFT',
                subscription_id=plan_pro_catalog.id,
                benefit_months=3,
                buyer=_buyer(),
                recipient=_recipient(),
                payment=_payment(),
                idempotency_key=f'idem-gift-{uuid.uuid4().hex}',
            )
        )
    voucher = PromotionVoucher.objects.get(serial=result.voucher_serial)
    assert voucher.scope == PromotionVoucher.Scope.OPEN
    assert voucher.origin == PromotionVoucher.Origin.PUBLIC_PURCHASE
    assert voucher.voucher_type == PromotionVoucher.VoucherType.GIFT
    assert result.amount_paid == Decimal('299')


@override_settings(PROMO_GIFT_CATALOG_JSON=_CATALOG)
def test_m4_checkout_discount_creates_open_voucher(plan_pro_catalog, company_a):
    with override_settings(PROMO_PUBLIC_BILLING_COMPANY_ID=str(company_a.id)):
        result = PublicPurchaseCheckoutUseCase().execute(
            PublicPurchaseCheckoutSchema(
                voucher_type='DISCOUNT',
                subscription_id=plan_pro_catalog.id,
                discount_percent=Decimal('20'),
                discount_duration_months=3,
                buyer=_buyer(),
                recipient=_recipient(),
                payment=_payment(),
                idempotency_key=f'idem-disc-{uuid.uuid4().hex}',
            )
        )
    voucher = PromotionVoucher.objects.get(serial=result.voucher_serial)
    assert voucher.voucher_type == PromotionVoucher.VoucherType.DISCOUNT


@override_settings(PROMO_GIFT_CATALOG_JSON=_CATALOG)
def test_m5_checkout_payment_failure_no_voucher(plan_pro_catalog, company_a):
    before = PromotionVoucher.objects.count()
    with override_settings(PROMO_PUBLIC_BILLING_COMPANY_ID=str(company_a.id)):
        with pytest.raises(Exception):
            PublicPurchaseCheckoutUseCase().execute(
                PublicPurchaseCheckoutSchema(
                    voucher_type='GIFT',
                    subscription_id=plan_pro_catalog.id,
                    benefit_months=3,
                    buyer=_buyer(),
                    recipient=_recipient(),
                    payment=_payment(card_number='4000000000000002'),
                    idempotency_key=f'idem-fail-{uuid.uuid4().hex}',
                )
            )
    assert PromotionVoucher.objects.count() == before


@override_settings(PROMO_GIFT_CATALOG_JSON=_CATALOG)
@patch('platform.features.billing.commerce.promotion.application.voucher_emails.threading.Thread')
@patch('platform.features.communication.notification.service.NotificationService.send_email')
def test_m6_m7_m8_public_purchase_emails(mock_send, mock_thread, plan_pro_catalog, company_a):
    def _run_inline(*, target, daemon=True):
        target()
        return MagicMock()

    mock_thread.side_effect = _run_inline
    recipient = _recipient()
    with override_settings(PROMO_PUBLIC_BILLING_COMPANY_ID=str(company_a.id)):
        PublicPurchaseCheckoutUseCase().execute(
            PublicPurchaseCheckoutSchema(
                voucher_type='GIFT',
                subscription_id=plan_pro_catalog.id,
                benefit_months=3,
                buyer=_buyer(),
                recipient=recipient,
                payment=_payment(),
                idempotency_key=f'idem-email-{uuid.uuid4().hex}',
            )
        )
    templates = {call.kwargs['template_code'] for call in mock_send.call_args_list}
    assert 'GIFT_VOUCHER' in templates
    assert mock_send.call_args_list[0].kwargs['to'] == [recipient.email]


@override_settings(PROMO_GIFT_CATALOG_JSON=_CATALOG)
@patch('platform.features.billing.commerce.promotion.application.voucher_emails.threading.Thread')
@patch(
    'platform.features.billing.commerce.invoice.application.send_invoice.SendInvoiceUseCase.execute',
)
def test_m8_buyer_receives_voucher_purchased_invoice(mock_send_invoice, mock_thread, plan_pro_catalog, company_a):
    def _run_inline(*, target, daemon=True):
        target()
        return MagicMock()

    mock_thread.side_effect = _run_inline
    buyer = _buyer()
    with override_settings(PROMO_PUBLIC_BILLING_COMPANY_ID=str(company_a.id)):
        PublicPurchaseCheckoutUseCase().execute(
            PublicPurchaseCheckoutSchema(
                voucher_type='GIFT',
                subscription_id=plan_pro_catalog.id,
                benefit_months=3,
                buyer=buyer,
                recipient=_recipient(),
                payment=_payment(),
                idempotency_key=f'idem-invoice-{uuid.uuid4().hex}',
            )
        )
    mock_send_invoice.assert_called_once()
    assert mock_send_invoice.call_args.args[1] == buyer.email
    assert mock_send_invoice.call_args.kwargs['email_context']['payment_status'] == 'Pagado'


@override_settings(PROMO_GIFT_CATALOG_JSON=_CATALOG)
def test_m9_no_payment_method_persisted(plan_pro_catalog, company_a):
    before = PaymentMethod.objects.count()
    with override_settings(PROMO_PUBLIC_BILLING_COMPANY_ID=str(company_a.id)):
        PublicPurchaseCheckoutUseCase().execute(
            PublicPurchaseCheckoutSchema(
                voucher_type='GIFT',
                subscription_id=plan_pro_catalog.id,
                benefit_months=3,
                buyer=_buyer(),
                recipient=_recipient(),
                payment=_payment(),
                idempotency_key=f'idem-pm-{uuid.uuid4().hex}',
            )
        )
    assert PaymentMethod.objects.count() == before


@override_settings(PROMO_GIFT_CATALOG_JSON=_CATALOG)
def test_m11_checkout_idempotent(plan_pro_catalog, company_a):
    key = f'idem-repeat-{uuid.uuid4().hex}'
    payload = PublicPurchaseCheckoutSchema(
        voucher_type='GIFT',
        subscription_id=plan_pro_catalog.id,
        benefit_months=3,
        buyer=_buyer(),
        recipient=_recipient(),
        payment=_payment(),
        idempotency_key=key,
    )
    with override_settings(PROMO_PUBLIC_BILLING_COMPANY_ID=str(company_a.id)):
        first = PublicPurchaseCheckoutUseCase().execute(payload)
        second = PublicPurchaseCheckoutUseCase().execute(payload)
    assert first.voucher_serial == second.voucher_serial
    assert PromotionVoucher.objects.filter(metadata__checkout_idempotency_key=key).count() == 1
