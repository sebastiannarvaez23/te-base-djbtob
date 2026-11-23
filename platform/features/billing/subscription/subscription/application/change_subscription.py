"""
ChangeSubscriptionUseCase — orquesta el cambio de plan con su lógica de
negocio: mejora (upgrade) vs relevo (downgrade), decidido por el precio.

  * UPGRADE (precio destino > actual): cobra el plan, aplica el cambio con
    nueva vigencia (30 días mensual / 365 anual) y envía SUB_UPGRADE con la
    factura adjunta. Si el cobro falla, revierte el cambio de plan.
  * DOWNGRADE (precio destino <= actual): NO cobra. Registra el plan como
    pendiente (el cliente conserva el plan actual hasta su vigencia) y envía
    SUB_DOWNGRADE. El cobro y la nueva vigencia ocurren al vencer, vía la
    tarea programada ``apply_pending_downgrades`` (que reusa
    ``apply_scheduled_change``).

El correo de upgrade se enruta por la metadata del cargo: ``InvoiceBillingListener``
la traslada al evento ``InvoiceIssued`` (``email_template_code`` /
``email_context``) y ``InvoiceDeliveryListener`` la pasa a ``SendInvoiceUseCase``.
"""
import logging
from datetime import datetime, timezone

from core.errors import AppErrorCode, AppException, NotFoundException

from platform.features.billing.commerce.payments.application.use_cases import CreateChargeUseCase
from platform.features.billing.commerce.payments.domain.enums import ChargeStatus

from ..domain.billing_cycle import MONTHLY, YEARLY, charge_amount, normalize_billing_interval
from ..domain.interfaces import ISubscriptionRepository
from .change_emails import build_downgrade_context, build_upgrade_context
from .charging import charge_plan
from core.trace import trace_layer

logger = logging.getLogger('app.api')


class ChangeSubscriptionUseCase:

    def __init__(
        self,
        subscription_repo: ISubscriptionRepository,
        charge_use_case: CreateChargeUseCase,
        notification=None,
        directory=None,
    ):
        self._repo = subscription_repo
        self._charge = charge_use_case
        if notification is None:
            from platform.features.communication.notification.service import NotificationService
            notification = NotificationService()
        self._notification = notification
        if directory is None:
            from platform.features.billing.common.directory import DjangoBillingDirectory
            directory = DjangoBillingDirectory()
        self._directory = directory

    def _annual_discount(self):
        try:
            return self._repo.get_annual_discount_percent()
        except Exception:
            return None

    # ── entry point ──────────────────────────────────────────────────────────

    @trace_layer('application')
    def execute(self, company_id, subscription_id, payment_method_id=None, billing_interval=None):
        # One change at a time: while a downgrade is pending (not yet active)
        # no further plan change is allowed until it activates.
        if self._repo.get_pending_change(company_id) is not None:
            raise AppException(
                AppErrorCode.SUB_CHANGE_ALREADY_PENDING,
            )

        target = self._repo.get_by_id(subscription_id)
        if target is None:
            raise NotFoundException(
                AppErrorCode.COMPANY_NOT_FOUND,
                override_detail='Subscription not found.',
            )

        current_plan_id = self._repo.active_plan_id(company_id)
        current = self._repo.get_by_id(current_plan_id) if current_plan_id else None
        current_interval = (
            self._repo.active_billing_interval(company_id) if current else MONTHLY
        )
        target_interval = (
            normalize_billing_interval(billing_interval)
            if billing_interval else current_interval
        )

        if current is not None and current.id == target.id:
            if target_interval == current_interval:
                return self._repo.get_active_acquisition(company_id)
            if target_interval == YEARLY:
                return self._do_upgrade(
                    company_id, target, current, payment_method_id, target_interval,
                )
            return self._do_downgrade(company_id, target, current, target_interval)

        # No active plan or a dearer *cycle charge* ⇒ upgrade (charge now).
        # Compare charge_amount (respects yearly discount), not monthly list price.
        percent = self._annual_discount()
        current_charge = (
            charge_amount(current.price, current_interval, percent)
            if current is not None
            else None
        )
        target_charge = charge_amount(target.price, target_interval, percent)
        is_upgrade = current is None or target_charge > current_charge
        if is_upgrade:
            return self._do_upgrade(
                company_id, target, current, payment_method_id, target_interval,
            )
        return self._do_downgrade(company_id, target, current, target_interval)

    # ── upgrade (charge + invoice + SUB_UPGRADE) ─────────────────────────────

    def _do_upgrade(self, company_id, target, current, payment_method_id, billing_interval):
        amount = charge_amount(target.price, billing_interval, self._annual_discount())
        # Free plan ⇒ just apply, no charge, no invoice.
        if amount is None or amount <= 0:
            result = self._repo.activate_plan(
                company_id, target.id, billing_interval=billing_interval,
            )
            self._forfeit_active_promotions(company_id)
            return result

        if not payment_method_id:
            raise AppException(
                AppErrorCode.PAY_GATEWAY_REJECTED,
                override_detail='A payment method is required for a paid plan.',
            )

        now = datetime.now(timezone.utc)
        email_ctx = build_upgrade_context(
            new_plan=target, previous_plan=current,
            admin=self._directory.admin_of(company_id),
            company=self._directory.company(company_id), now=now,
            charge_amount=amount, billing_interval=billing_interval,
        )
        result = self._charge_and_activate(
            company_id, target, previous_plan_id=(current.id if current else None),
            previous_interval=(
                self._repo.active_billing_interval(company_id) if current else MONTHLY
            ),
            payment_method_id=payment_method_id,
            billing_interval=billing_interval,
            amount=amount,
            charge_metadata={
                'email_template_code': 'SUB_UPGRADE',
                'email_context': email_ctx,
                'billing_interval': billing_interval,
            },
            description=f'Mejora a {target.name}',
        )
        self._forfeit_active_promotions(company_id)
        return result

    # ── downgrade (no charge; scheduled until vigencia) ──────────────────────

    def _do_downgrade(self, company_id, target, current, billing_interval):
        result = self._repo.set_pending_downgrade(
            company_id, target.id, billing_interval=billing_interval,
        )
        # Do NOT forfeit gifts/discounts here — customer keeps current plan (and
        # its promo) until vigencia. Forfeit runs when the downgrade materialises.

        admin = self._directory.admin_of(company_id)
        ctx = build_downgrade_context(
            new_plan=target, previous_plan=current, admin=admin,
            company=self._directory.company(company_id), now=datetime.now(timezone.utc),
            charge_amount=charge_amount(target.price, billing_interval, self._annual_discount()),
            billing_interval=billing_interval,
        )
        if admin is not None and getattr(admin, 'email', ''):
            self._notification.send_email(
                template_code='SUB_DOWNGRADE', to=[admin.email], context=ctx,
            )
        return result

    # ── scheduled application (called by the Celery task at vigencia) ────────

    @trace_layer('application')
    def apply_scheduled_change(self, company_id, subscription_id, payment_method_id,
                               billing_interval=None):
        """Charge + activate a plan unconditionally (no upgrade/downgrade
        detection). Used to materialise a pending downgrade when it expires;
        the payment sends the default invoice email (SUB_INVOICING)."""
        target = self._repo.get_by_id(subscription_id)
        if target is None:
            raise NotFoundException(
                AppErrorCode.COMPANY_NOT_FOUND,
                override_detail='Subscription not found.',
            )
        interval = normalize_billing_interval(billing_interval)
        amount = charge_amount(target.price, interval, self._annual_discount())
        if amount is None or amount <= 0:
            result = self._repo.activate_plan(
                company_id, target.id, billing_interval=interval,
            )
            self._forfeit_active_promotions(company_id)
            return result
        result = self._charge_and_activate(
            company_id, target, previous_plan_id=self._repo.active_plan_id(company_id),
            previous_interval=self._repo.active_billing_interval(company_id),
            payment_method_id=payment_method_id,
            billing_interval=interval,
            amount=amount,
            charge_metadata={'billing_interval': interval},
            description=f'Suscripción {target.name}',
        )
        self._forfeit_active_promotions(company_id)
        return result

    # ── shared charge+activate (upgrade-first so the auto-invoice links new) ─

    def _charge_and_activate(self, company_id, target, *, previous_plan_id,
                             previous_interval, payment_method_id, billing_interval,
                             amount, charge_metadata, description):
        result = self._repo.activate_plan(
            company_id, target.id, billing_interval=billing_interval,
        )
        try:
            charge = charge_plan(
                self._charge, company_id,
                amount=amount, payment_method_id=payment_method_id,
                metadata=charge_metadata, description=description,
                currency=getattr(target, 'currency', '') or '',
            )
        except Exception:
            self._rollback(company_id, previous_plan_id, previous_interval)
            raise

        if charge.status != ChargeStatus.CAPTURED:
            self._rollback(company_id, previous_plan_id, previous_interval)
            raise AppException(
                AppErrorCode.PAY_GATEWAY_REJECTED,
                override_detail=(
                    getattr(charge, 'failure_message', '')
                    or 'El pago no pudo procesarse; no se cambió el plan.'
                ),
            )
        return result

    def _rollback(self, company_id, previous_plan_id, previous_interval):
        if previous_plan_id is not None:
            self._repo.activate_plan(
                company_id, previous_plan_id, billing_interval=previous_interval,
            )

    @staticmethod
    def _forfeit_active_promotions(company_id) -> None:
        try:
            from platform.features.billing.commerce.promotion import composition as promo
            promo.forfeit_active_promotion_benefits(company_id)
        except Exception:
            logger.exception(
                'failed to forfeit promotion benefits after plan change for company %s',
                company_id,
            )
