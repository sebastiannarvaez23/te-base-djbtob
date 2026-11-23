"""
RenewSubscriptionUseCase — automatic recurring renewal of the active plan.

When an active acquisition reaches its end_date with no pending change and
``auto_renew`` on, this charges the SAME plan and extends the vigencia (30
days monthly / 365 yearly, matching the stored billing interval). The charge
drives the usual invoice + SUB_INVOICING email + attached PDF. If the charge
fails (or there's no card on file), the subscription is suspended and a
SUB_SUSPENDED email is sent.

Same shape as ApplyPendingDowngradesUseCase: a per-company unit of work the
task layer wraps in a per-company lock (shared with the downgrade/expiry
processing) so no double-charge can happen.
"""
import logging
from datetime import datetime, timezone

from platform.features.billing.commerce.payments.application.use_cases import CreateChargeUseCase
from platform.features.billing.commerce.payments.domain.enums import ChargeStatus

from ..domain.billing_cycle import charge_amount
from .change_emails import build_suspended_context
from .charging import charge_plan
from core.trace import trace_layer

logger = logging.getLogger('app.tasks')


class RenewSubscriptionUseCase:

    def __init__(
        self,
        repo,
        charge_use_case: CreateChargeUseCase,
        notification=None,
        directory=None,
    ):
        self._repo = repo
        self._charge = charge_use_case
        if notification is None:
            from platform.features.communication.notification.service import NotificationService
            notification = NotificationService()
        self._notification = notification
        if directory is None:
            from platform.features.billing.common.directory import DjangoBillingDirectory
            directory = DjangoBillingDirectory()
        self._directory = directory

    @trace_layer('application')
    def due_company_ids(self):
        return self._repo.list_renewals_due()

    @trace_layer('application')
    def renew_for_company(self, company_id) -> str:
        """Charge + extend the active plan for ONE company. Idempotent: re-reads
        the renewal-due plan, so once extended (new acquisition, future
        end_date) a second call is a no-op.

        Returns 'renewed', 'suspended' or 'not_due'.
        """
        plan_id = self._repo.get_renewal_due(company_id)
        if plan_id is None:
            return 'not_due'
        plan = self._repo.get_by_id(plan_id)
        if plan is None:
            return 'not_due'

        interval = self._repo.active_billing_interval(company_id)
        percent = self._repo.get_annual_discount_percent()
        cycle_amount = charge_amount(plan.price, interval, percent)

        # Free plan: extend without charge.
        if cycle_amount is None or cycle_amount <= 0:
            self._repo.activate_plan(company_id, plan_id, billing_interval=interval)
            return 'renewed'

        from platform.features.billing.commerce.promotion import composition as promo

        amount, promo_meta, skip_charge = promo.get_renewal_charge_amount(
            company_id, cycle_amount, plan_id=plan_id,
        )
        if skip_charge:
            self._repo.activate_plan(company_id, plan_id, billing_interval=interval)
            return 'renewed'

        card = self._directory.active_card(company_id)
        if card is None:
            self._suspend(company_id, plan, cycle_amount, interval)
            return 'suspended'

        # Charge FIRST so the auto-created invoice links the active plan; the
        # capture fires PaymentCaptured → invoice + SUB_INVOICING (default
        # template) + attached PDF. Then extend the vigencia.
        metadata = dict(promo_meta or {})
        metadata.setdefault('billing_interval', interval)
        try:
            charge = charge_plan(
                self._charge, company_id,
                amount=amount, payment_method_id=card.id,
                metadata=metadata,
                description=f'Renovación {plan.name}',
                currency=getattr(plan, 'currency', '') or '',
            )
        except Exception:
            logger.exception('renewal charge errored for company %s', company_id)
            self._suspend(company_id, plan, cycle_amount, interval)
            return 'suspended'

        if charge.status != ChargeStatus.CAPTURED:
            self._suspend(company_id, plan, cycle_amount, interval)
            return 'suspended'

        self._repo.activate_plan(
            company_id, plan_id, billing_interval=interval, charge_id=charge.id,
        )
        promo.after_successful_renewal_charge(company_id, plan_id=plan_id)
        return 'renewed'

    def _suspend(self, company_id, plan, cycle_amount, interval) -> None:
        self._repo.suspend(company_id)
        admin = self._directory.admin_of(company_id)
        if admin is not None and getattr(admin, 'email', ''):
            ctx = build_suspended_context(
                plan=plan, admin=admin,
                company=self._directory.company(company_id),
                now=datetime.now(timezone.utc),
                charge_amount=cycle_amount, billing_interval=interval,
            )
            self._notification.send_email(
                template_code='SUB_SUSPENDED', to=[admin.email], context=ctx,
            )
