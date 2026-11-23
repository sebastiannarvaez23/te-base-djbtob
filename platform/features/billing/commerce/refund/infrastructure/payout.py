"""Payout adapter: money goes through the same IPaymentGateway as charges.

A future Stripe/Wompi refund adapter implements ``IRefundPayoutPort`` the
same way ``IPaymentGateway`` is registered — swap this class at the
composition root. While ``SIMULATE_PAYMENT=True`` the charge factory
returns ``SimulatedGateway.refund_charge``.
"""
import uuid
from decimal import Decimal

from core.errors import AppException

from platform.features.billing.commerce.payments.application.use_cases import RefundChargeUseCase

from ..domain.interfaces import IRefundPayoutPort
from ..domain.schemas import PayoutResult


class ChargeGatewayRefundAdapter(IRefundPayoutPort):
    def __init__(self, refund_charge: RefundChargeUseCase):
        self._refund_charge = refund_charge

    def refund(self, charge_id: uuid.UUID, amount: Decimal, reason: str) -> PayoutResult:
        try:
            charge = self._refund_charge.execute(charge_id, amount=amount, reason=reason)
        except AppException as exc:
            return PayoutResult(ok=False, error=getattr(exc.code, 'value', str(exc.code)))
        except Exception as exc:
            return PayoutResult(ok=False, error=str(exc)[:512])
        refunded = getattr(charge, 'refunded_amount', amount)
        return PayoutResult(
            ok=True,
            refunded_amount=amount,
            gateway_refund_id=charge.gateway_charge_id or '',
        )
