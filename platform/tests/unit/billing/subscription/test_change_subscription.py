"""High-precision unit tests for the subscription-change use cases.

This is a delicate, money-touching flow, so the tests assert not only the
happy path but the *exact* behaviour: operation ORDER (plan applied before the
charge so the auto-invoice links the new plan), exact charge arguments, precise
rollback on failure, and the "must-not-happen" guarantees of each branch
(downgrade never charges, a failed upgrade never leaves the new plan active,
the scheduled task never double-processes, etc.).

All collaborators are mocked — no DB, no gateway, no event bus, no email.
"""
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, call, patch

from core.errors import AppErrorCode, AppException, NotFoundException

from platform.features.billing.commerce.payments.domain.enums import ChargeStatus, MethodType
from platform.features.billing.subscription.subscription.domain.schemas import PendingDowngradeDueSchema
from platform.features.billing.subscription.subscription.application.change_subscription import (
    ChangeSubscriptionUseCase,
)
from platform.features.billing.subscription.subscription.application.apply_pending_downgrades import (
    ApplyPendingDowngradesUseCase,
)


def _plan(price, name='Plan', features=None):
    return SimpleNamespace(id=uuid.uuid4(), name=name,
                           price=Decimal(str(price)), features=features or [])


def _charge(status=ChargeStatus.CAPTURED, failure_message=''):
    return SimpleNamespace(status=status, failure_message=failure_message)


def _result(name='Plan'):
    return SimpleNamespace(subscription_name=name, status='active')


_UNSET = object()   # lets a test inject admin/company=None explicitly


class _Base(TestCase):
    def setUp(self):
        self.repo = MagicMock()
        self.charge = MagicMock()
        self.notification = MagicMock()
        self.admin = SimpleNamespace(first_name='Ana', last_name='Gómez', email='admin@acme.com')
        self.company = SimpleNamespace(name='Acme S.A.S')
        self.company_id = uuid.uuid4()
        self.repo.activate_plan.return_value = _result()
        self.charge.execute.return_value = _charge(ChargeStatus.CAPTURED)
        self.repo.get_pending_change.return_value = None   # no change in flight by default
        self.repo.active_billing_interval.return_value = 'monthly'
        self.repo.pending_billing_interval.return_value = 'monthly'
        self.repo.get_active_acquisition.return_value = _result()
        self.repo.get_annual_discount_percent.return_value = Decimal('15')
        self._gift_patcher = patch(
            'platform.features.billing.commerce.promotion.composition.forfeit_active_promotion_benefits',
            return_value=0,
        )
        self.forfeit_gift = self._gift_patcher.start()
        self.addCleanup(self._gift_patcher.stop)

    def _uc(self, admin=_UNSET, company=_UNSET):
        directory = MagicMock()
        directory.admin_of.return_value = self.admin if admin is _UNSET else admin
        directory.company.return_value = self.company if company is _UNSET else company
        return ChangeSubscriptionUseCase(
            self.repo, self.charge, notification=self.notification, directory=directory,
        )

    def _wire(self, target, current=None):
        plans = {target.id: target}
        if current:
            plans[current.id] = current
        self.repo.get_by_id.side_effect = lambda i: plans.get(i)
        self.repo.active_plan_id.return_value = current.id if current else None


# ── Entry point / direction detection ─────────────────────────────────────────

class TestDirectionDetection(_Base):

    def test_unknown_plan_raises_not_found(self):
        self.repo.get_by_id.side_effect = lambda i: None
        with self.assertRaises(NotFoundException) as ctx:
            self._uc().execute(self.company_id, uuid.uuid4())
        self.assertEqual(ctx.exception.code, AppErrorCode.COMPANY_NOT_FOUND)
        self.repo.activate_plan.assert_not_called()
        self.charge.execute.assert_not_called()
        self.repo.set_pending_downgrade.assert_not_called()

    def test_no_current_plan_is_treated_as_upgrade(self):
        target = _plan(50, 'Pro')
        self._wire(target, current=None)
        self._uc().execute(self.company_id, target.id, payment_method_id=uuid.uuid4())
        self.charge.execute.assert_called_once()
        self.repo.set_pending_downgrade.assert_not_called()

    def test_dearer_target_is_upgrade(self):
        current, target = _plan(30, 'Basic'), _plan(50, 'Pro')
        self._wire(target, current=current)
        self._uc().execute(self.company_id, target.id, payment_method_id=uuid.uuid4())
        self.charge.execute.assert_called_once()
        self.repo.set_pending_downgrade.assert_not_called()

    def test_cheaper_target_is_downgrade(self):
        current, target = _plan(80, 'Enterprise'), _plan(30, 'Pro')
        self._wire(target, current=current)
        self._uc().execute(self.company_id, target.id, payment_method_id=uuid.uuid4())
        self.repo.set_pending_downgrade.assert_called_once()
        self.charge.execute.assert_not_called()

    def test_equal_price_is_downgrade_path_no_charge(self):
        current, target = _plan(50, 'A'), _plan(50, 'B')
        self._wire(target, current=current)
        self._uc().execute(self.company_id, target.id, payment_method_id=uuid.uuid4())
        self.repo.set_pending_downgrade.assert_called_once()
        self.charge.execute.assert_not_called()
        self.repo.activate_plan.assert_not_called()

    def test_reads_target_then_current(self):
        current, target = _plan(30), _plan(50)
        self._wire(target, current=current)
        self._uc().execute(self.company_id, target.id, payment_method_id=uuid.uuid4())
        self.repo.active_plan_id.assert_called_once_with(self.company_id)

    def test_cheaper_monthly_list_but_dearer_yearly_charge_is_upgrade(self):
        """Enterprise monthly ($150) → Pro yearly (~$1020) must charge now."""
        current, target = _plan(150, 'Enterprise'), _plan(100, 'Pro')
        self._wire(target, current=current)
        self.repo.active_billing_interval.return_value = 'monthly'
        self._uc().execute(
            self.company_id, target.id,
            payment_method_id=uuid.uuid4(),
            billing_interval='yearly',
        )
        self.charge.execute.assert_called_once()
        self.repo.set_pending_downgrade.assert_not_called()
        amount = self.charge.execute.call_args.args[0].amount
        self.assertEqual(amount, Decimal('1020.00'))

    def test_dearer_monthly_list_but_cheaper_cycle_charge_is_downgrade(self):
        """Pro yearly (~$1020) → Enterprise monthly ($150) schedules downgrade."""
        current, target = _plan(100, 'Pro'), _plan(150, 'Enterprise')
        self._wire(target, current=current)
        self.repo.active_billing_interval.return_value = 'yearly'
        self._uc().execute(
            self.company_id, target.id,
            payment_method_id=uuid.uuid4(),
            billing_interval='monthly',
        )
        self.repo.set_pending_downgrade.assert_called_once()
        self.charge.execute.assert_not_called()


# ── Upgrade ───────────────────────────────────────────────────────────────────

class TestUpgrade(_Base):

    def test_applies_plan_before_charging(self):
        """Order matters: the plan must be active before the charge fires
        PaymentCaptured, or the auto-invoice would link the OLD plan."""
        order = []
        target = _plan(50, 'Pro')
        self._wire(target, current=None)
        self.repo.activate_plan.side_effect = lambda *a, **k: order.append('upgrade') or _result()
        self.charge.execute.side_effect = lambda *a, **k: order.append('charge') or _charge()

        self._uc().execute(self.company_id, target.id, payment_method_id=uuid.uuid4())

        self.assertEqual(order, ['upgrade', 'charge'])

    def test_charge_request_has_exact_amount_method_and_payment_method(self):
        target = _plan(Decimal('49.99'), 'Pro')
        self._wire(target, current=None)
        pm = uuid.uuid4()

        self._uc().execute(self.company_id, target.id, payment_method_id=pm)

        args, kwargs = self.charge.execute.call_args
        request = args[0]
        self.assertEqual(request.amount, Decimal('49.99'))
        self.assertEqual(request.method_type, MethodType.CARD)
        self.assertEqual(kwargs['company_id'], self.company_id)
        self.assertEqual(kwargs['payment_method_id'], pm)

    def test_charge_metadata_routes_sub_upgrade_with_full_context(self):
        current, target = _plan(30, 'Basic'), _plan(50, 'Pro')
        self._wire(target, current=current)

        self._uc().execute(self.company_id, target.id, payment_method_id=uuid.uuid4())

        meta = self.charge.execute.call_args.args[0].metadata
        self.assertEqual(meta['email_template_code'], 'SUB_UPGRADE')
        ctx = meta['email_context']
        self.assertEqual(ctx['new_plan'], 'Pro')
        self.assertEqual(ctx['new_price'], 50.0)
        self.assertEqual(ctx['previous_plan'], 'Basic')
        self.assertEqual(ctx['user_name'], 'Ana Gómez')
        self.assertEqual(ctx['company_name'], 'Acme S.A.S')

    def test_success_upgrades_exactly_once_and_returns_result(self):
        target = _plan(50, 'Pro')
        self._wire(target, current=None)
        sentinel = _result('Pro')
        self.repo.activate_plan.return_value = sentinel

        result = self._uc().execute(self.company_id, target.id, payment_method_id=uuid.uuid4())

        self.repo.activate_plan.assert_called_once_with(
            self.company_id, target.id, billing_interval='monthly',
        )
        self.assertIs(result, sentinel)
        self.notification.send_email.assert_not_called()   # upgrade email goes via the chain
        self.forfeit_gift.assert_called_once_with(self.company_id)

    def test_paid_without_payment_method_raises_and_never_touches_state(self):
        target = _plan(50, 'Pro')
        self._wire(target, current=None)
        with self.assertRaises(AppException) as ctx:
            self._uc().execute(self.company_id, target.id, payment_method_id=None)
        self.assertEqual(ctx.exception.code, AppErrorCode.PAY_GATEWAY_REJECTED)
        self.repo.activate_plan.assert_not_called()
        self.charge.execute.assert_not_called()
        self.forfeit_gift.assert_not_called()

    def test_free_upgrade_applies_without_charge_or_email(self):
        target = _plan(0, 'Free')
        self._wire(target, current=None)
        self._uc().execute(self.company_id, target.id)
        self.repo.activate_plan.assert_called_once_with(
            self.company_id, target.id, billing_interval='monthly',
        )
        self.charge.execute.assert_not_called()
        self.notification.send_email.assert_not_called()
        self.forfeit_gift.assert_called_once_with(self.company_id)

    def test_declined_charge_rolls_back_to_previous_in_order(self):
        order = []
        current, target = _plan(30, 'Basic'), _plan(50, 'Pro')
        self._wire(target, current=current)
        self.repo.activate_plan.side_effect = lambda cid, pid, **k: order.append(pid) or _result()
        self.charge.execute.return_value = _charge(ChargeStatus.FAILED, 'tarjeta declinada')

        with self.assertRaises(AppException) as ctx:
            self._uc().execute(self.company_id, target.id, payment_method_id=uuid.uuid4())

        self.assertEqual(ctx.exception.code, AppErrorCode.PAY_GATEWAY_REJECTED)
        self.assertIn('declinada', ctx.exception.detail)
        # applied new, then rolled back to old — exactly these two, in order
        self.assertEqual(order, [target.id, current.id])
        self.forfeit_gift.assert_not_called()

    def test_declined_charge_without_previous_plan_does_not_roll_back(self):
        target = _plan(50, 'Pro')
        self._wire(target, current=None)
        self.charge.execute.return_value = _charge(ChargeStatus.FAILED)

        with self.assertRaises(AppException):
            self._uc().execute(self.company_id, target.id, payment_method_id=uuid.uuid4())

        # only the initial apply — nothing to roll back to
        self.repo.activate_plan.assert_called_once_with(
            self.company_id, target.id, billing_interval='monthly',
        )

    def test_gateway_exception_rolls_back_and_propagates_original(self):
        order = []
        current, target = _plan(30, 'Basic'), _plan(50, 'Pro')
        self._wire(target, current=current)
        self.repo.activate_plan.side_effect = lambda cid, pid, **k: order.append(pid) or _result()
        boom = RuntimeError('gateway boom')
        self.charge.execute.side_effect = boom

        with self.assertRaises(RuntimeError) as ctx:
            self._uc().execute(self.company_id, target.id, payment_method_id=uuid.uuid4())

        self.assertIs(ctx.exception, boom)            # original error, not wrapped
        self.assertEqual(order, [target.id, current.id])


# ── Downgrade ─────────────────────────────────────────────────────────────────

class TestDowngrade(_Base):

    def setUp(self):
        super().setUp()
        self.current, self.target = _plan(80, 'Enterprise'), _plan(30, 'Pro')
        self._wire(self.target, current=self.current)

    def test_records_pending_and_never_charges_or_changes_plan(self):
        self._uc().execute(self.company_id, self.target.id, payment_method_id=uuid.uuid4())
        self.repo.set_pending_downgrade.assert_called_once_with(
            self.company_id, self.target.id, billing_interval='monthly',
        )
        self.charge.execute.assert_not_called()
        self.repo.activate_plan.assert_not_called()
        # Gift/discount stay until the pending downgrade materialises.
        self.forfeit_gift.assert_not_called()

    def test_returns_unchanged_current_acquisition(self):
        sentinel = _result('Enterprise')
        self.repo.set_pending_downgrade.return_value = sentinel
        result = self._uc().execute(self.company_id, self.target.id)
        self.assertIs(result, sentinel)

    def test_sends_sub_downgrade_email_to_admin_with_context(self):
        self._uc().execute(self.company_id, self.target.id)
        _, kwargs = self.notification.send_email.call_args
        self.assertEqual(kwargs['template_code'], 'SUB_DOWNGRADE')
        self.assertEqual(kwargs['to'], ['admin@acme.com'])
        self.assertEqual(kwargs['context']['new_plan'], 'Pro')
        self.assertEqual(kwargs['context']['previous_plan'], 'Enterprise')

    def test_no_admin_skips_email_but_still_records_pending(self):
        self._uc(admin=None).execute(self.company_id, self.target.id)
        self.repo.set_pending_downgrade.assert_called_once()
        self.notification.send_email.assert_not_called()

    def test_admin_without_email_skips_email(self):
        admin = SimpleNamespace(first_name='A', last_name='B', email='')
        self._uc(admin=admin).execute(self.company_id, self.target.id)
        self.notification.send_email.assert_not_called()


# ── Scheduled application (used by the Celery task) ───────────────────────────

class TestScheduledApplication(_Base):

    def test_unknown_plan_raises(self):
        self.repo.get_by_id.return_value = None
        with self.assertRaises(NotFoundException):
            self._uc().apply_scheduled_change(self.company_id, uuid.uuid4(), uuid.uuid4())

    def test_charges_and_activates_with_default_email(self):
        order = []
        target = _plan(30, 'Pro')
        self.repo.get_by_id.return_value = target
        self.repo.active_plan_id.return_value = None
        self.repo.activate_plan.side_effect = lambda *a, **k: order.append('upgrade') or _result()
        self.charge.execute.side_effect = lambda *a, **k: order.append('charge') or _charge()

        self._uc().apply_scheduled_change(self.company_id, target.id, uuid.uuid4())

        self.assertEqual(order, ['upgrade', 'charge'])
        # NO SUB_UPGRADE routing — the scheduled charge uses the default invoice email
        self.assertEqual(
            self.charge.execute.call_args.args[0].metadata,
            {'billing_interval': 'monthly'},
        )

    def test_free_pending_plan_activates_without_charge(self):
        target = _plan(0, 'Free')
        self.repo.get_by_id.return_value = target
        self._uc().apply_scheduled_change(self.company_id, target.id, uuid.uuid4())
        self.repo.activate_plan.assert_called_once_with(
            self.company_id, target.id, billing_interval='monthly',
        )
        self.charge.execute.assert_not_called()

    def test_declined_scheduled_charge_rolls_back(self):
        order = []
        target = _plan(30, 'Pro')
        old_id = uuid.uuid4()
        self.repo.get_by_id.return_value = target
        self.repo.active_plan_id.return_value = old_id
        self.repo.activate_plan.side_effect = lambda cid, pid, **k: order.append(pid) or _result()
        self.charge.execute.return_value = _charge(ChargeStatus.FAILED)

        with self.assertRaises(AppException):
            self._uc().apply_scheduled_change(self.company_id, target.id, uuid.uuid4())

        self.assertEqual(order, [target.id, old_id])


# ── ApplyPendingDowngradesUseCase (the task body) ─────────────────────────────

class TestBlockWhilePending(_Base):
    """Single-change-at-a-time: no plan change while a downgrade is pending."""

    def test_change_blocked_when_one_is_already_pending(self):
        self.repo.get_pending_change.return_value = {
            'type': 'downgrade', 'from_plan': 'Pro', 'to_plan': 'Std',
        }
        with self.assertRaises(AppException) as ctx:
            self._uc().execute(self.company_id, uuid.uuid4(), payment_method_id=uuid.uuid4())
        self.assertEqual(ctx.exception.code, AppErrorCode.SUB_CHANGE_ALREADY_PENDING)
        # nothing else happened
        self.repo.get_by_id.assert_not_called()
        self.charge.execute.assert_not_called()
        self.repo.set_pending_downgrade.assert_not_called()

    def test_pending_is_checked_before_anything_else(self):
        self.repo.get_pending_change.return_value = {'type': 'downgrade'}
        with self.assertRaises(AppException):
            self._uc().execute(self.company_id, uuid.uuid4())
        self.repo.get_pending_change.assert_called_once_with(self.company_id)


class TestApplyForCompany(TestCase):
    """Per-company unit of work shared by the daily sweep and the lazy task."""

    def setUp(self):
        self.repo = MagicMock()
        self.change = MagicMock()
        self.repo.pending_billing_interval.return_value = 'monthly'

    def _uc(self, card=_UNSET):
        directory = MagicMock()
        directory.active_card.return_value = SimpleNamespace(id='card') if card is _UNSET else card
        return ApplyPendingDowngradesUseCase(self.repo, self.change, directory)

    def test_due_company_ids_maps_repo_rows(self):
        c1, c2 = uuid.uuid4(), uuid.uuid4()
        self.repo.list_pending_downgrades_due.return_value = [
            PendingDowngradeDueSchema(company_id=c1, pending_subscription_id=uuid.uuid4()),
            PendingDowngradeDueSchema(company_id=c2, pending_subscription_id=uuid.uuid4()),
        ]
        self.assertEqual(self._uc().due_company_ids(), [c1, c2])

    def test_applies_with_due_plan_and_card(self):
        cid, plan = uuid.uuid4(), uuid.uuid4()
        self.repo.get_due_pending_downgrade.return_value = plan
        applied = self._uc(card=SimpleNamespace(id='card9')).apply_for_company(cid)
        self.assertTrue(applied)
        self.change.apply_scheduled_change.assert_called_once_with(
            cid, plan, 'card9', billing_interval='monthly',
        )

    def test_noop_when_not_due(self):
        """Idempotency anchor: if the switch already happened, nothing to do."""
        self.repo.get_due_pending_downgrade.return_value = None
        applied = self._uc().apply_for_company(uuid.uuid4())
        self.assertFalse(applied)
        self.change.apply_scheduled_change.assert_not_called()

    def test_skips_when_no_payment_method(self):
        self.repo.get_due_pending_downgrade.return_value = uuid.uuid4()
        applied = self._uc(card=None).apply_for_company(uuid.uuid4())
        self.assertFalse(applied)
        self.change.apply_scheduled_change.assert_not_called()

    def test_charge_error_propagates_to_task_layer(self):
        self.repo.get_due_pending_downgrade.return_value = uuid.uuid4()
        self.change.apply_scheduled_change.side_effect = RuntimeError('gateway boom')
        with self.assertRaises(RuntimeError):
            self._uc().apply_for_company(uuid.uuid4())


class TestChangeStatusUseCase(TestCase):
    """Read model for the settings UI (can_change + pending change details)."""

    def setUp(self):
        from platform.features.billing.subscription.subscription.application.use_cases import (
            GetSubscriptionChangeStatusUseCase,
        )
        self.repo = MagicMock()
        self.uc = GetSubscriptionChangeStatusUseCase(self.repo)

    def test_can_change_when_no_pending(self):
        self.repo.get_pending_change.return_value = None
        self.assertEqual(
            self.uc.execute(uuid.uuid4()),
            {'can_change': True, 'pending_change': None},
        )

    def test_blocked_with_details_and_formatted_date(self):
        from datetime import datetime, timezone as tz
        self.repo.get_pending_change.return_value = {
            'type': 'downgrade', 'from_plan': 'Enterprise', 'to_plan': 'Standard',
            'activates_on': datetime(2026, 7, 28, tzinfo=tz.utc),
        }
        result = self.uc.execute(uuid.uuid4())
        self.assertFalse(result['can_change'])
        self.assertEqual(result['pending_change']['from_plan'], 'Enterprise')
        self.assertEqual(result['pending_change']['to_plan'], 'Standard')
        self.assertEqual(result['pending_change']['activates_on'], '28/07/2026')   # %d/%m/%Y
        self.assertEqual(result['pending_change']['billing_interval'], 'monthly')

    def test_blocked_accepts_pending_change_schema(self):
        from datetime import datetime, timezone as tz
        from platform.features.billing.subscription.subscription.domain.schemas import PendingChangeSchema
        self.repo.get_pending_change.return_value = PendingChangeSchema(
            type='downgrade',
            from_plan='Enterprise',
            to_plan='Standard',
            activates_on=datetime(2026, 7, 28, tzinfo=tz.utc),
            billing_interval='yearly',
        )
        result = self.uc.execute(uuid.uuid4())
        self.assertFalse(result['can_change'])
        self.assertEqual(result['pending_change']['activates_on'], '28/07/2026')
        self.assertEqual(result['pending_change']['billing_interval'], 'yearly')
        self.assertEqual(result['pending_change']['type'], 'downgrade')


class TestYearlyBilling(_Base):
    """Paying annually charges 12 × monthly with 15% off and stores yearly."""

    def test_upgrade_charges_yearly_amount(self):
        target = _plan(Decimal('100.00'), 'Pro')
        self._wire(target, current=None)
        pm = uuid.uuid4()

        self._uc().execute(
            self.company_id, target.id, payment_method_id=pm, billing_interval='yearly',
        )

        request = self.charge.execute.call_args.args[0]
        self.assertEqual(request.amount, Decimal('1020.00'))
        self.repo.activate_plan.assert_called_once_with(
            self.company_id, target.id, billing_interval='yearly',
        )

    def test_same_plan_monthly_to_yearly_is_upgrade(self):
        current = _plan(Decimal('50.00'), 'Pro')
        self._wire(current, current=current)
        self.repo.active_billing_interval.return_value = 'monthly'
        pm = uuid.uuid4()

        self._uc().execute(
            self.company_id, current.id, payment_method_id=pm, billing_interval='yearly',
        )

        request = self.charge.execute.call_args.args[0]
        self.assertEqual(request.amount, Decimal('510.00'))
        self.repo.set_pending_downgrade.assert_not_called()

    def test_same_plan_yearly_to_monthly_is_scheduled(self):
        current = _plan(Decimal('50.00'), 'Pro')
        self._wire(current, current=current)
        self.repo.active_billing_interval.return_value = 'yearly'

        self._uc().execute(
            self.company_id, current.id, payment_method_id=uuid.uuid4(),
            billing_interval='monthly',
        )

        self.repo.set_pending_downgrade.assert_called_once_with(
            self.company_id, current.id, billing_interval='monthly',
        )
        self.charge.execute.assert_not_called()

    def test_same_plan_same_interval_is_noop(self):
        current = _plan(Decimal('50.00'), 'Pro')
        self._wire(current, current=current)
        sentinel = _result('Pro')
        self.repo.get_active_acquisition.return_value = sentinel

        result = self._uc().execute(
            self.company_id, current.id, payment_method_id=uuid.uuid4(),
            billing_interval='monthly',
        )

        self.assertIs(result, sentinel)
        self.charge.execute.assert_not_called()
        self.repo.activate_plan.assert_not_called()
        self.repo.set_pending_downgrade.assert_not_called()
