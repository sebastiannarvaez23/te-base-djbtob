"""
Retry payment for a suspended subscription (billing recovery).

After a failed renewal charge the acquisition is ``suspended``. The company
admin can add/update a card and call this use case to charge again and
restore full access.
"""
import logging

from core.access.billing_recovery import is_company_admin
from core.errors import (
    AppErrorCode,
    AppException,
    NotFoundException,
    PermissionException,
    SubscriptionException,
    ValidationAppException,
)
from platform.features.billing.commerce.payments.application.use_cases import CreateChargeUseCase
from platform.features.billing.commerce.payments.domain.enums import ChargeStatus
from platform.features.billing.subscription.subscription.application.charging import charge_plan
from platform.features.billing.subscription.subscription.domain.billing_cycle import charge_amount
from platform.features.billing.subscription.subscription.domain.interfaces import ISubscriptionRepository
from platform.features.billing.subscription.subscription.domain.schemas import (
    CompanySubscriptionResultSchema,
    RetrySuspendedPaymentInputSchema,
)
from core.trace import trace_layer

logger = logging.getLogger('app.api')


class RetrySuspendedPaymentUseCase:

    def __init__(
        self,
        repo: ISubscriptionRepository,
        charge_use_case: CreateChargeUseCase,
        directory=None,
    ):
        self._repo = repo
        self._charge = charge_use_case
        if directory is None:
            from platform.features.billing.common.directory import DjangoBillingDirectory
            directory = DjangoBillingDirectory()
        self._directory = directory

    @trace_layer('application')
    def execute(
        self,
        data: RetrySuspendedPaymentInputSchema,
        *,
        actor_user,
    ) -> CompanySubscriptionResultSchema:
        """Charge the suspended plan and reactivate access."""
        if not is_company_admin(actor_user):
            raise PermissionException(AppErrorCode.PERM_INSUFFICIENT)

        if data.access_mode != 'billing_recovery':
            raise SubscriptionException(AppErrorCode.SUB_NO_ACTIVE)

        company_id = data.company_id
        suspended = self._repo.get_suspended_acquisition(company_id, for_update=True)
        if suspended is None:
            active = self._repo.get_active_acquisition(company_id)
            if active is not None:
                return active
            raise NotFoundException(AppErrorCode.SUB_NO_SUSPENDED)

        plan = self._repo.get_by_id(suspended.subscription_id)
        if plan is None:
            raise NotFoundException(
                AppErrorCode.SUB_NO_SUSPENDED,
                override_detail='The suspended subscription plan could not be found.',
            )

        interval = suspended.billing_interval
        percent = self._repo.get_annual_discount_percent()
        cycle_amount = charge_amount(plan.price, interval, percent)

        if cycle_amount is None or cycle_amount <= 0:
            restored = self._repo.restore_after_payment(company_id, charge_id=None)
            if restored is None:
                raise NotFoundException(AppErrorCode.SUB_NO_SUSPENDED)
            return restored

        card_id = data.payment_method_id
        if card_id is None:
            card = self._directory.active_card(company_id)
            if card is None:
                raise ValidationAppException(
                    AppErrorCode.VALIDATION_ERROR,
                    override_detail='A registered payment method is required to retry billing.',
                )
            card_id = card.id

        from platform.features.billing.commerce.promotion import composition as promo

        amount, promo_meta, skip_charge = promo.get_renewal_charge_amount(
            company_id, cycle_amount, plan_id=suspended.subscription_id,
        )
        if skip_charge:
            restored = self._repo.restore_after_payment(company_id, charge_id=None)
            if restored is None:
                raise NotFoundException(AppErrorCode.SUB_NO_SUSPENDED)
            return restored

        metadata = dict(promo_meta or {})
        metadata.setdefault('billing_interval', interval)
        metadata['billing_recovery'] = True
        metadata['suspended_period_id'] = str(suspended.id)

        try:
            charge = charge_plan(
                self._charge, company_id,
                amount=amount, payment_method_id=card_id,
                metadata=metadata,
                description=f'Reactivación {plan.name}',
                currency=getattr(plan, 'currency', '') or '',
            )
        except Exception:
            logger.exception('billing recovery charge errored for company %s', company_id)
            raise AppException(
                AppErrorCode.PAY_GATEWAY_REJECTED,
                override_detail='The payment could not be processed. Check your payment method and try again.',
            )

        if charge.status != ChargeStatus.CAPTURED:
            raise AppException(
                AppErrorCode.PAY_GATEWAY_REJECTED,
                override_detail='The payment could not be processed. Check your payment method and try again.',
            )

        restored = self._repo.restore_after_payment(company_id, charge_id=charge.id)
        if restored is None:
            active = self._repo.get_active_acquisition(company_id)
            if active is not None:
                return active
            raise NotFoundException(AppErrorCode.SUB_NO_SUSPENDED)

        promo.after_successful_renewal_charge(company_id, plan_id=suspended.subscription_id)
        return restored
