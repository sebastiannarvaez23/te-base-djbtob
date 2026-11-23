"""Post-finalize billing hooks for onboarding with promotions.

``OnboardingBillingService`` orchestrates redeem/charge/payment-method purely
through injected ports; ``process_onboarding_billing`` is the composition-wired
facade the client onboarding flow calls.

Behavior preserved:
  * GIFT (or zero final) redeems without a card; charge only if a token exists.
  * Paid DISCOUNT: charge FIRST, then redeem (fail-closed — no unpaid benefit).
"""

import logging
import uuid
from decimal import Decimal

from core.errors import AppErrorCode, AppException
from core.trace import trace_layer

from ..domain.interfaces import IPlanCatalogPort, IPromotionChargePort
from ..domain.schemas import ChargeSnapshot, RedeemVoucherSchema

logger = logging.getLogger('app.api')


def _requires_payment(preview: dict, sub_data: dict) -> bool:
    """Paid promo or paid plan must not redeem without a successful charge path."""
    voucher_type = (preview.get('voucher_type') or '').upper()
    if voucher_type == 'GIFT':
        return False
    final = Decimal(str(preview.get(
        'final_amount',
        sub_data.get('charge_amount', sub_data.get('price', 0) or 0),
    )))
    return final > 0


class OnboardingBillingService:
    def __init__(
        self,
        *,
        redeem_use_case,
        charge_port: IPromotionChargePort,
        payment_method_creator,
        plan_catalog: IPlanCatalogPort,
    ):
        self._redeem = redeem_use_case
        self._charge = charge_port
        self._pm_creator = payment_method_creator
        self._plan_catalog = plan_catalog

    def _plan_name(self, subscription_id: uuid.UUID) -> str:
        try:
            plan = self._plan_catalog.get_active_plan(subscription_id)
            return getattr(plan, 'name', '') or 'Suscripción'
        except Exception:
            return 'Suscripción'

    def _redeem_voucher(
        self,
        *,
        serial: str,
        subscription_id: uuid.UUID,
        company_id: uuid.UUID,
        registration_id: uuid.UUID,
    ):
        return self._redeem.execute(
            RedeemVoucherSchema(
                serial=serial,
                subscription_id=subscription_id,
                company_id=company_id,
                context='ONBOARDING',
                idempotency_key=f'onb-{registration_id}',
            )
        )

    def _bind_charge_to_period(self, company_id: uuid.UUID, charge: ChargeSnapshot) -> None:
        if charge.id is None:
            return
        try:
            self._charge.bind_to_active_period(company_id=company_id, charge_id=charge.id)
        except Exception:
            # Cobro already captured; bind is bookkeeping for refunds — fail-open.
            logger.exception(
                'onboarding billing: failed to bind promo charge company=%s charge=%s',
                company_id, charge.id,
            )

    @trace_layer('application')
    def run(self, *, company_id: uuid.UUID, registration) -> None:
        sub_data = registration.subscription_data or {}
        payment_data = registration.payment_data or {}
        serial = sub_data.get('applied_voucher_serial')
        preview = sub_data.get('promotion_preview') or {}

        has_serial = bool(serial and registration.subscription_id)
        has_token = bool(payment_data.get('processor_token'))

        if not has_serial and not has_token:
            return

        paid_promo = has_serial and _requires_payment(preview, sub_data)
        if paid_promo and not has_token:
            logger.error(
                'onboarding billing: refusing unpaid discount redeem company=%s serial=%s',
                company_id, serial,
            )
            raise AppException(
                AppErrorCode.PAY_GATEWAY_REJECTED,
                override_detail='A payment method is required to redeem a paid promotional voucher.',
            )

        redemption_id = None
        if has_serial and not paid_promo:
            try:
                result = self._redeem_voucher(
                    serial=serial,
                    subscription_id=registration.subscription_id,
                    company_id=company_id,
                    registration_id=registration.id,
                )
                redemption_id = result.redemption.id
                preview = result.preview.model_dump(mode='json')
            except Exception:
                logger.exception('onboarding voucher redeem failed company=%s', company_id)
                raise

        if not has_token:
            if has_serial:
                logger.info(
                    'onboarding billing: gift redeemed without payment method company=%s serial=%s',
                    company_id, serial,
                )
            return

        pm_id = self._pm_creator.create_from_onboarding(company_id=company_id, payment_data=payment_data)

        final_amount = Decimal(str(preview.get(
            'final_amount',
            sub_data.get('charge_amount', sub_data.get('price', 0) or 0),
        )))
        original_amount = Decimal(str(preview.get(
            'original_amount',
            sub_data.get('charge_amount', sub_data.get('price', 0) or 0),
        )))
        discount_amount = Decimal(str(preview.get('discount_amount', 0) or 0))
        sub_name = self._plan_name(registration.subscription_id)
        billing_interval = str(sub_data.get('billing_interval') or 'monthly')
        promo_email = {
            'promotion_serial': serial or '',
            'promotion_voucher_type': preview.get('voucher_type', ''),
            'promotion_original_amount': float(original_amount),
            'promotion_discount_amount': float(discount_amount),
            'billing_interval': billing_interval,
        }

        # Paid discount: charge first, then redeem so a failed charge never grants benefit.
        if paid_promo:
            try:
                charge = self._charge.charge_plan(
                    company_id=company_id,
                    amount=final_amount,
                    payment_method_id=pm_id,
                    metadata={
                        'promotion_serial': serial or '',
                        'voucher_type': preview.get('voucher_type', ''),
                        'original_amount': str(original_amount),
                        'discount_amount': str(discount_amount),
                        'billing_interval': billing_interval,
                        'email_context': promo_email,
                    },
                    description=f'Registro — {sub_name}',
                )
                if not charge.is_captured:
                    raise AppException(
                        AppErrorCode.PAY_GATEWAY_REJECTED,
                        override_detail=(
                            charge.failure_message
                            or 'El pago no pudo procesarse; no se aplicó el bono.'
                        ),
                    )
            except Exception:
                logger.exception('onboarding paid promo charge failed company=%s', company_id)
                raise

            self._redeem_voucher(
                serial=serial,
                subscription_id=registration.subscription_id,
                company_id=company_id,
                registration_id=registration.id,
            )
            self._bind_charge_to_period(company_id, charge)
            return

        # Optional charge after gift redeem (amount often 0).
        try:
            self._charge.charge_plan(
                company_id=company_id,
                amount=final_amount,
                payment_method_id=pm_id,
                metadata={
                    'promotion_redemption_id': str(redemption_id) if redemption_id else '',
                    'promotion_serial': serial or '',
                    'voucher_type': preview.get('voucher_type', ''),
                    'original_amount': str(original_amount),
                    'discount_amount': str(discount_amount),
                    'billing_interval': billing_interval,
                    'email_context': promo_email,
                },
                description=f'Registro — {sub_name}',
            )
        except Exception:
            logger.exception('onboarding charge failed company=%s', company_id)
            raise
