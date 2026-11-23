"""Charge adapter — the promotion feature's single door into billing/payments."""

import logging
import uuid
from decimal import Decimal
from typing import Optional

from platform.features.billing.commerce.promotion.domain.interfaces import IPromotionChargePort
from platform.features.billing.commerce.promotion.domain.schemas import ChargeSnapshot

logger = logging.getLogger('billing.promotion')


class DjangoPromotionCharge(IPromotionChargePort):

    def charge_plan(
        self,
        *,
        company_id: uuid.UUID,
        amount: Decimal,
        payment_method_id: Optional[uuid.UUID] = None,
        metadata: dict,
        description: str,
        processor_token: Optional[str] = None,
        card_data: Optional[dict] = None,
        buyer_name: str = '',
        buyer_email: str = '',
        idempotency_key: Optional[str] = None,
        currency: str = 'USD',
    ) -> ChargeSnapshot:
        from platform.features.billing.commerce.payments.application.use_cases import CreateChargeUseCase
        from platform.features.billing.commerce.payments.domain.enums import MethodType
        from platform.features.billing.commerce.payments.domain.schemas import CardData, ChargeRequest, PayerRef
        from platform.features.billing.commerce.payments.infrastructure.repositories import DjangoChargeRepository
        from platform.features.billing.commerce.payments.infrastructure.routing.router import DefaultPaymentRouter
        from platform.features.billing.commerce.payments.integration.adapters.country_currency_policy import (
            DjangoCountryCurrencyPolicy,
        )

        card = CardData(**card_data) if card_data else None
        request = ChargeRequest(
            payer=PayerRef(
                company_id=company_id,
                display_name=buyer_name or '',
                email=buyer_email or '',
            ),
            amount=amount,
            currency=currency,
            method_type=MethodType.CARD,
            description=description,
            gateway_payment_method_id=processor_token or '',
            card=card,
            metadata=metadata,
        )
        charge = CreateChargeUseCase(
            DjangoChargeRepository(),
            DefaultPaymentRouter(),
            currency_policy=DjangoCountryCurrencyPolicy(),
        ).execute(
            request,
            company_id=company_id,
            idempotency_key=idempotency_key,
            payment_method_id=payment_method_id,
        )
        status = getattr(charge.status, 'value', charge.status)
        return ChargeSnapshot(
            id=charge.id,
            status=str(status),
            failure_message=getattr(charge, 'failure_message', '') or '',
        )

    def bind_to_active_period(self, *, company_id: uuid.UUID, charge_id: uuid.UUID) -> None:
        from platform.features.billing.commerce.payments.application.bind_period import BindChargeToPeriodUseCase
        from platform.features.billing.commerce.payments.infrastructure.repositories import DjangoChargeRepository
        from platform.features.billing.subscription.subscription.infrastructure.active_period import (
            DjangoActivePeriodLookup,
        )

        period = DjangoActivePeriodLookup().get(company_id)
        if period is None:
            logger.warning(
                'promo charge bind skipped: no active period company=%s charge=%s',
                company_id, charge_id,
            )
            return
        BindChargeToPeriodUseCase(DjangoChargeRepository()).execute(charge_id, period.id)
