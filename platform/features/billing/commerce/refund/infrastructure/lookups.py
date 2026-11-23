import uuid
from typing import Any, Mapping, Optional

from platform.features.billing.commerce.payments.domain.enums import ChargeStatus
from platform.features.billing.commerce.payments.models import Charge
from platform.features.billing.subscription.subscription.models import CompanySubscription

from ..domain.interfaces import IPeriodSnapshotLookup, IRefundableChargeLookup
from ..domain.schemas import PeriodSnapshot, RefundableCharge

_REFUNDABLE = (ChargeStatus.CAPTURED.value, ChargeStatus.PARTIALLY_REFUNDED.value)
_CHARGE_FIELDS = ('id', 'amount', 'refunded_amount', 'currency', 'status')


def _refundable(row: Optional[Mapping[str, Any]]) -> Optional[RefundableCharge]:
    if row is None:
        return None
    charge = RefundableCharge(**row)
    if charge.remaining <= 0:
        return None
    return charge


class DjangoPeriodSnapshotLookup(IPeriodSnapshotLookup):
    def get_active(self, company_id: uuid.UUID) -> Optional[PeriodSnapshot]:
        cs = (
            CompanySubscription.objects
            .select_related('subscription')
            .filter(company_id=company_id, status=CompanySubscription.Status.ACTIVE)
            .order_by('-start_date')
            .first()
        )
        if cs is None:
            return None
        return PeriodSnapshot(
            id=cs.id,
            company_id=cs.company_id,
            subscription_id=cs.subscription_id,
            subscription_name=cs.subscription.name,
            start_date=cs.start_date,
            price_paid=cs.price_paid,
            billing_interval=cs.billing_interval,
            status=cs.status,
        )


class DjangoRefundableChargeLookup(IRefundableChargeLookup):
    def get_for_period(self, company_id: uuid.UUID, period_id: uuid.UUID) -> Optional[RefundableCharge]:
        qs = Charge.objects.filter(company_id=company_id, status__in=_REFUNDABLE)
        bound = (
            qs.filter(company_subscription_id=period_id)
            .order_by('-captured_at', '-created_at')
            .values(*_CHARGE_FIELDS)
            .first()
        )
        if bound is not None:
            return _refundable(bound)
        # Only an unbound cobro (never another period's payment). Promo
        # onboarding may charge before activate_plan; bind_to_active_period
        # stamps it afterwards. If that stamp is missing, the row stays null.
        unbound = (
            qs.filter(company_subscription_id__isnull=True)
            .order_by('-captured_at', '-created_at')
            .values(*_CHARGE_FIELDS)
            .first()
        )
        return _refundable(unbound)
