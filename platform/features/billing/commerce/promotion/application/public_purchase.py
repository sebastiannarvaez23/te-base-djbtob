"""Public voucher purchase preview + checkout (Fase 5).

All dependencies are injected — no composition/service-locator imports.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from core.errors import AppErrorCode, ConflictException, ValidationAppException

from ..domain.interfaces import (
    IBillingCompanyPort,
    IInvoiceBridgePort,
    INotificationPort,
    IPlanCatalogPort,
    IPromotionChargePort,
    IPromotionVoucherRepository,
)
from ..domain.schemas import (
    PublicPurchaseCheckoutResultSchema,
    PublicPurchaseCheckoutSchema,
    PublicPurchasePreviewRequestSchema,
    PublicPurchasePreviewResponseSchema,
)
from .purchase_catalog import lookup_discount_price, lookup_gift_price
from .voucher_emails import (
    EmailConfig,
    build_public_purchase_charge_metadata,
    dispatch_public_purchase_buyer_invoice,
    dispatch_public_purchase_emails,
)
from core.trace import trace_layer

logger = logging.getLogger('app.api')


def _checkout_result_from_voucher(voucher) -> PublicPurchaseCheckoutResultSchema:
    metadata = voucher.metadata or {}
    charge_raw = metadata.get('charge_id')
    return PublicPurchaseCheckoutResultSchema(
        voucher_serial=voucher.serial,
        redeem_valid_until=voucher.redeem_valid_until,
        amount_paid=Decimal(str(metadata.get('amount_paid', 0))),
        charge_id=uuid.UUID(str(charge_raw)) if charge_raw else None,
    )


class PublicPurchasePreviewUseCase:
    def __init__(
        self,
        *,
        plan_catalog: IPlanCatalogPort,
        catalog: dict,
        currency: str = 'USD',
    ):
        self._plan_catalog = plan_catalog
        self._catalog = catalog
        self._currency = currency

    @trace_layer('application')
    def execute(self, data: PublicPurchasePreviewRequestSchema) -> PublicPurchasePreviewResponseSchema:
        plan = self._plan_catalog.get_active_plan(data.subscription_id)
        if data.voucher_type == 'GIFT':
            if not data.benefit_months:
                raise ValidationAppException(AppErrorCode.PROMO_INVALID_INPUT)
            match = lookup_gift_price(
                plan=plan,
                benefit_months=data.benefit_months,
                catalog=self._catalog,
                currency=self._currency,
            )
        elif data.voucher_type == 'DISCOUNT':
            if data.discount_percent is None or not data.discount_duration_months:
                raise ValidationAppException(AppErrorCode.PROMO_INVALID_INPUT)
            match = lookup_discount_price(
                plan=plan,
                discount_percent=data.discount_percent,
                discount_duration_months=data.discount_duration_months,
                catalog=self._catalog,
                currency=self._currency,
            )
        else:
            raise ValidationAppException(AppErrorCode.PROMO_INCOMPATIBLE)

        return PublicPurchasePreviewResponseSchema(
            amount=match.amount,
            currency=match.currency,
            description=match.description,
        )


class PublicPurchaseCheckoutUseCase:
    def __init__(
        self,
        *,
        repository: IPromotionVoucherRepository,
        charge_port: IPromotionChargePort,
        billing_company: IBillingCompanyPort,
        invoice_bridge: IInvoiceBridgePort,
        notifier: INotificationPort,
        plan_catalog: IPlanCatalogPort,
        catalog: dict,
        redeem_months: int,
        email_config: EmailConfig,
        currency: str = 'USD',
    ):
        self._repo = repository
        self._charge = charge_port
        self._billing_company = billing_company
        self._invoice_bridge = invoice_bridge
        self._notifier = notifier
        self._preview = PublicPurchasePreviewUseCase(
            plan_catalog=plan_catalog,
            catalog=catalog,
            currency=currency,
        )
        self._redeem_months = redeem_months
        self._email_config = email_config

    @trace_layer('application')
    def execute(self, data: PublicPurchaseCheckoutSchema) -> PublicPurchaseCheckoutResultSchema:
        existing = self._repo.find_by_checkout_idempotency(data.idempotency_key)
        if existing is not None:
            return _checkout_result_from_voucher(existing)

        preview = self._preview.execute(
            PublicPurchasePreviewRequestSchema(
                voucher_type=data.voucher_type,
                subscription_id=data.subscription_id,
                benefit_months=data.benefit_months,
                discount_percent=data.discount_percent,
                discount_duration_months=data.discount_duration_months,
            )
        )

        company_id = self._billing_company.resolve_public_billing_company_id()
        charge = self._run_charge(
            company_id=company_id,
            amount=preview.amount,
            currency=preview.currency,
            description=preview.description,
            idempotency_key=data.idempotency_key,
            payment=data.payment,
            buyer=data.buyer,
            subscription_id=data.subscription_id,
        )

        if not charge.is_captured:
            raise ValidationAppException(
                AppErrorCode.PAY_GATEWAY_REJECTED,
                override_detail=charge.failure_message or 'Payment was not captured.',
            )

        existing = self._repo.find_by_checkout_idempotency(data.idempotency_key)
        if existing is not None:
            return _checkout_result_from_voucher(existing)

        now = datetime.now(timezone.utc)
        redeem_until = now + relativedelta(months=self._redeem_months)
        metadata = {
            'checkout_idempotency_key': data.idempotency_key,
            'amount_paid': str(preview.amount),
            'charge_id': str(charge.id),
            'buyer': data.buyer.model_dump(mode='json'),
            'recipient': data.recipient.model_dump(mode='json'),
        }

        try:
            voucher = self._repo.create_public_purchase_voucher(
                voucher_type=data.voucher_type,
                subscription_id=data.subscription_id,
                benefit_months=data.benefit_months,
                discount_percent=data.discount_percent,
                discount_duration_months=data.discount_duration_months or 1,
                redeem_valid_from=now,
                redeem_valid_until=redeem_until,
                metadata=metadata,
                recipient_message=data.recipient.message or '',
                checkout_idempotency_key=data.idempotency_key,
            )
        except ConflictException:
            existing = self._repo.find_by_checkout_idempotency(data.idempotency_key)
            if existing is not None:
                return _checkout_result_from_voucher(existing)
            raise

        dispatch_public_purchase_emails(
            notifier=self._notifier,
            voucher=voucher,
            buyer=data.buyer,
            recipient=data.recipient,
            amount_paid=preview.amount,
            currency=preview.currency,
            config=self._email_config,
        )
        dispatch_public_purchase_buyer_invoice(
            bridge=self._invoice_bridge,
            notifier=self._notifier,
            charge_id=charge.id,
            voucher=voucher,
            buyer=data.buyer,
            recipient=data.recipient,
            amount_paid=preview.amount,
            currency=preview.currency,
            idempotency_key=data.idempotency_key,
            config=self._email_config,
        )

        return PublicPurchaseCheckoutResultSchema(
            voucher_serial=voucher.serial,
            redeem_valid_until=voucher.redeem_valid_until,
            amount_paid=preview.amount,
            charge_id=charge.id,
        )

    def _run_charge(
        self,
        *,
        company_id,
        amount,
        currency,
        description,
        idempotency_key,
        payment,
        buyer,
        subscription_id,
    ):
        card_data = None
        card_number = (getattr(payment, 'card_number', '') or '').replace(' ', '')
        if card_number:
            card_data = {
                'number': card_number,
                'exp_month': payment.expiry_month,
                'exp_year': payment.expiry_year,
                'cvc': '123',
                'holder_name': payment.holder,
            }
        elif payment.processor_token.startswith('decline'):
            card_data = {'number': '4000000000000002'}

        return self._charge.charge_plan(
            company_id=company_id,
            amount=amount,
            currency=currency,
            description=description,
            processor_token=payment.processor_token,
            card_data=card_data,
            buyer_name=buyer.name,
            buyer_email=buyer.email,
            idempotency_key=idempotency_key,
            metadata=build_public_purchase_charge_metadata(
                buyer=buyer, subscription_id=subscription_id,
            ),
        )
