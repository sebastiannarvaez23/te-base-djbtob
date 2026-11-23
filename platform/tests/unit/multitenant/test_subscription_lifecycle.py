"""
Subscription lifecycle tests in a multitenant context.

Verifies the business rules for CompanySubscription status transitions:
  - ACTIVE → CANCELLED  (cancellation)
  - CANCELLED → ACTIVE  (reactivation, only if not expired)
  - ACTIVE → CLOSED + new ACTIVE  (upgrade / renew)

After the Clean Architecture refactor:
  - Views delegate to use cases (tested by mocking use case classes at the api module).
  - ORM business rules live in DjangoSubscriptionRepository. CompanySubscription and
    timezone are locally imported inside each method, so they are patched at their
    source modules (subscription.models and django.utils).
"""
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest import TestCase
from unittest.mock import MagicMock, patch

_NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=dt_timezone.utc)
_30_DAYS = _NOW + timedelta(days=30)

from platform.features.billing.subscription.subscription.domain.events import PeriodClosed, PeriodIssued
from platform.features.billing.subscription.subscription.domain.schemas import CompanySubscriptionResultSchema
from core.errors.exceptions import NotFoundException


def _cs_result(**overrides) -> CompanySubscriptionResultSchema:
    defaults = dict(
        id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
        subscription_name='Pro Plan',
        start_date=_NOW,
        ends_at=_30_DAYS,
        status='active',
    )
    defaults.update(overrides)
    return CompanySubscriptionResultSchema(**defaults)


def _prepare_activate_mocks(MockCS, new_cs, sub):
    qs = MockCS.objects.filter.return_value
    qs.values_list.return_value = []
    new_cs.start_date = _NOW
    new_cs.end_date = _30_DAYS
    new_cs.subscription = sub
    new_cs.billing_interval = getattr(new_cs, 'billing_interval', 'monthly')


# ── UpgradeView: HTTP contract ─────────────────────────────────────────────────

class TestUpgradeViewHTTP(TestCase):
    """
    UpgradeView delegates to ChangeSubscriptionUseCase.
    Tests verify the HTTP status codes returned by the view.
    """

    @patch('platform.features.billing.subscription.subscription.presentation.api.DjangoSubscriptionRepository')
    @patch('platform.features.billing.subscription.subscription.presentation.api.ChangeSubscriptionUseCase')
    def test_upgrade_returns_201_on_success(self, MockUseCase, MockRepo):
        from platform.features.billing.subscription.subscription.presentation.api import UpgradeView

        MockUseCase.return_value.execute.return_value = _cs_result(status='active')

        request = MagicMock()
        request.data = {'subscription_id': str(uuid.uuid4())}
        request.tenant = MagicMock()

        response = UpgradeView().post(request)

        self.assertEqual(response.status_code, 201)

    @patch('platform.features.billing.subscription.subscription.presentation.api.DjangoSubscriptionRepository')
    @patch('platform.features.billing.subscription.subscription.presentation.api.ChangeSubscriptionUseCase')
    def test_upgrade_without_subscription_id_returns_400(self, MockUseCase, MockRepo):
        from platform.features.billing.subscription.subscription.presentation.api import UpgradeView

        request = MagicMock()
        request.data = {}  # no subscription_id

        response = UpgradeView().post(request)

        self.assertEqual(response.status_code, 400)
        MockUseCase.return_value.execute.assert_not_called()

    @patch('platform.features.billing.subscription.subscription.presentation.api.DjangoSubscriptionRepository')
    @patch('platform.features.billing.subscription.subscription.presentation.api.ChangeSubscriptionUseCase')
    def test_upgrade_to_nonexistent_plan_raises_not_found(self, MockUseCase, MockRepo):
        from platform.features.billing.subscription.subscription.presentation.api import UpgradeView

        MockUseCase.return_value.execute.return_value = None

        request = MagicMock()
        request.data = {'subscription_id': str(uuid.uuid4())}
        request.tenant = MagicMock()

        with self.assertRaises(NotFoundException):
            UpgradeView().post(request)

    @patch('platform.features.billing.subscription.subscription.presentation.api.DjangoSubscriptionRepository')
    @patch('platform.features.billing.subscription.subscription.presentation.api.ChangeSubscriptionUseCase')
    def test_upgrade_forwards_company_and_subscription_ids_to_use_case(self, MockUseCase, MockRepo):
        from platform.features.billing.subscription.subscription.presentation.api import UpgradeView

        MockUseCase.return_value.execute.return_value = _cs_result()
        sub_id = uuid.uuid4()
        request = MagicMock()
        request.data = {'subscription_id': str(sub_id)}
        request.tenant.id = uuid.uuid4()

        UpgradeView().post(request)

        MockUseCase.return_value.execute.assert_called_once_with(
            company_id=request.tenant.id,
            subscription_id=sub_id,
            payment_method_id=None,
            billing_interval=None,
        )


# ── CancelView: HTTP contract ──────────────────────────────────────────────────

class TestCancelViewHTTP(TestCase):

    @patch('platform.features.billing.subscription.subscription.presentation.api.DjangoSubscriptionRepository')
    @patch('platform.features.billing.subscription.subscription.presentation.api.CancelSubscriptionUseCase')
    def test_cancel_returns_200_on_success(self, MockUseCase, MockRepo):
        from platform.features.billing.subscription.subscription.presentation.api import CancelView

        MockUseCase.return_value.execute.return_value = _cs_result(status='cancelled')

        response = CancelView().post(MagicMock())

        self.assertEqual(response.status_code, 200)

    @patch('platform.features.billing.subscription.subscription.presentation.api.DjangoSubscriptionRepository')
    @patch('platform.features.billing.subscription.subscription.presentation.api.CancelSubscriptionUseCase')
    def test_cancel_without_active_subscription_raises_not_found(self, MockUseCase, MockRepo):
        from platform.features.billing.subscription.subscription.presentation.api import CancelView

        MockUseCase.return_value.execute.return_value = None

        with self.assertRaises(NotFoundException):
            CancelView().post(MagicMock())

    @patch('platform.features.billing.subscription.subscription.presentation.api.DjangoSubscriptionRepository')
    @patch('platform.features.billing.subscription.subscription.presentation.api.CancelSubscriptionUseCase')
    def test_cancel_forwards_company_id_to_use_case(self, MockUseCase, MockRepo):
        from platform.features.billing.subscription.subscription.presentation.api import CancelView

        MockUseCase.return_value.execute.return_value = _cs_result()
        company_id = uuid.uuid4()
        request = MagicMock()
        request.tenant.id = company_id

        CancelView().post(request)

        MockUseCase.return_value.execute.assert_called_once_with(company_id=company_id)


# ── ReactivateView: HTTP contract ──────────────────────────────────────────────

class TestReactivateViewHTTP(TestCase):

    @patch('platform.features.billing.subscription.subscription.presentation.api.DjangoSubscriptionRepository')
    @patch('platform.features.billing.subscription.subscription.presentation.api.ReactivateSubscriptionUseCase')
    def test_reactivate_returns_200_on_success(self, MockUseCase, MockRepo):
        from platform.features.billing.subscription.subscription.presentation.api import ReactivateView

        MockUseCase.return_value.execute.return_value = _cs_result(status='active')

        response = ReactivateView().post(MagicMock())

        self.assertEqual(response.status_code, 200)

    @patch('platform.features.billing.subscription.subscription.presentation.api.DjangoSubscriptionRepository')
    @patch('platform.features.billing.subscription.subscription.presentation.api.ReactivateSubscriptionUseCase')
    def test_reactivate_expired_subscription_raises_not_found(self, MockUseCase, MockRepo):
        from platform.features.billing.subscription.subscription.presentation.api import ReactivateView

        MockUseCase.return_value.execute.return_value = None

        with self.assertRaises(NotFoundException):
            ReactivateView().post(MagicMock())

    @patch('platform.features.billing.subscription.subscription.presentation.api.DjangoSubscriptionRepository')
    @patch('platform.features.billing.subscription.subscription.presentation.api.ReactivateSubscriptionUseCase')
    def test_reactivate_forwards_company_id_to_use_case(self, MockUseCase, MockRepo):
        from platform.features.billing.subscription.subscription.presentation.api import ReactivateView

        MockUseCase.return_value.execute.return_value = _cs_result()
        company_id = uuid.uuid4()
        request = MagicMock()
        request.tenant.id = company_id

        ReactivateView().post(request)

        MockUseCase.return_value.execute.assert_called_once_with(company_id=company_id)


# ── repo.activate_plan: business rules ────────────────────────────────────────
# CompanySubscription and timezone are locally imported inside each repository
# method, so patches must target the source modules directly.

class TestUpgradeBusinessRules(TestCase):
    """
    On upgrade:
    1. All ACTIVE periods for the company are closed (not cancelled).
    2. A new CompanySubscription is created with status ACTIVE and 30 days.
    3. The price paid reflects the current plan price.
    """

    @patch('django.utils.timezone')
    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    @patch('platform.features.billing.subscription.subscription.infrastructure.repositories.Subscription')
    def test_upgrade_cancels_active_and_creates_new(self, MockSub, MockCS, mock_tz):
        from platform.features.billing.subscription.subscription.infrastructure.repositories import DjangoSubscriptionRepository

        mock_tz.now.return_value = _NOW
        sub_id = uuid.uuid4()
        sub = MagicMock()
        sub.id = sub_id
        sub.name = 'Pro Plan'
        sub.price = Decimal('99.99')
        MockSub.objects.get.return_value = sub

        cs_id = uuid.uuid4()
        new_cs = MagicMock()
        new_cs.id = cs_id
        new_cs.end_date.strftime.return_value = '01/07/2025'
        new_cs.status = 'ACTIVE'
        MockCS.objects.create.return_value = new_cs
        MockCS.Status.ACTIVE = 'ACTIVE'
        MockCS.Status.CLOSED = 'CLOSED'
        MockCS.Status.CANCELLED = 'CANCELLED'
        _prepare_activate_mocks(MockCS, new_cs, sub)

        company_id = uuid.uuid4()
        DjangoSubscriptionRepository().activate_plan(company_id, sub_id)

        # Previous active period is closed (fulfilled / superseded), not cancelled
        MockCS.objects.filter.assert_called_with(
            company_id=company_id,
            status='ACTIVE',
        )
        MockCS.objects.filter.return_value.update.assert_called_with(status='CLOSED')
        MockCS.objects.create.assert_called_once()

    @patch('django.utils.timezone')
    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    @patch('platform.features.billing.subscription.subscription.infrastructure.repositories.Subscription')
    def test_upgrade_price_paid_reflects_current_plan_price(self, MockSub, MockCS, mock_tz):
        from platform.features.billing.subscription.subscription.infrastructure.repositories import DjangoSubscriptionRepository

        mock_tz.now.return_value = _NOW
        sub = MagicMock()
        sub.id = uuid.uuid4()
        sub.name = 'Pro Plan'
        sub.price = Decimal('149.99')
        MockSub.objects.get.return_value = sub
        MockCS.Status.ACTIVE = 'ACTIVE'
        MockCS.Status.CLOSED = 'CLOSED'
        MockCS.Status.CANCELLED = 'CANCELLED'
        new_cs = MagicMock()
        new_cs.id = uuid.uuid4()
        new_cs.status = 'ACTIVE'
        MockCS.objects.create.return_value = new_cs
        _prepare_activate_mocks(MockCS, new_cs, sub)

        DjangoSubscriptionRepository().activate_plan(uuid.uuid4(), uuid.uuid4())

        kwargs = MockCS.objects.create.call_args.kwargs
        self.assertEqual(kwargs['price_paid'], Decimal('149.99'))

    @patch('django.utils.timezone')
    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    @patch('platform.features.billing.subscription.subscription.infrastructure.repositories.Subscription')
    def test_upgrade_creates_new_subscription_with_30_day_duration(self, MockSub, MockCS, mock_tz):
        from platform.features.billing.subscription.subscription.infrastructure.repositories import DjangoSubscriptionRepository

        mock_tz.now.return_value = _NOW
        sub = MagicMock()
        sub.id = uuid.uuid4()
        sub.name = 'Pro Plan'
        sub.price = Decimal('99.99')
        MockSub.objects.get.return_value = sub
        MockCS.Status.ACTIVE = 'ACTIVE'
        MockCS.Status.CLOSED = 'CLOSED'
        MockCS.Status.CANCELLED = 'CANCELLED'
        new_cs = MagicMock()
        new_cs.id = uuid.uuid4()
        new_cs.status = 'ACTIVE'
        MockCS.objects.create.return_value = new_cs
        _prepare_activate_mocks(MockCS, new_cs, sub)

        DjangoSubscriptionRepository().activate_plan(uuid.uuid4(), uuid.uuid4())

        kwargs = MockCS.objects.create.call_args.kwargs
        self.assertEqual(kwargs['start_date'], _NOW)
        self.assertEqual(kwargs['end_date'], _30_DAYS)
        self.assertEqual(kwargs['billing_interval'], 'monthly')

    @patch('django.utils.timezone')
    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    @patch('platform.features.billing.subscription.subscription.infrastructure.repositories.Subscription')
    def test_upgrade_creates_yearly_subscription_with_365_day_duration(self, MockSub, MockCS, mock_tz):
        from platform.features.billing.subscription.subscription.infrastructure.repositories import DjangoSubscriptionRepository

        mock_tz.now.return_value = _NOW
        sub = MagicMock()
        sub.id = uuid.uuid4()
        sub.name = 'Pro Plan'
        sub.price = Decimal('100.00')
        MockSub.objects.get.return_value = sub
        MockCS.Status.ACTIVE = 'ACTIVE'
        MockCS.Status.CLOSED = 'CLOSED'
        MockCS.Status.CANCELLED = 'CANCELLED'
        new_cs = MagicMock()
        new_cs.id = uuid.uuid4()
        new_cs.status = 'ACTIVE'
        MockCS.objects.create.return_value = new_cs
        _prepare_activate_mocks(MockCS, new_cs, sub)

        DjangoSubscriptionRepository().activate_plan(
            uuid.uuid4(), uuid.uuid4(), billing_interval='yearly',
        )

        kwargs = MockCS.objects.create.call_args.kwargs
        self.assertEqual(kwargs['end_date'], _NOW + timedelta(days=365))
        self.assertEqual(kwargs['price_paid'], Decimal('1020.00'))
        self.assertEqual(kwargs['billing_interval'], 'yearly')

    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    @patch('platform.features.billing.subscription.subscription.infrastructure.repositories.Subscription')
    def test_upgrade_to_nonexistent_plan_returns_none(self, MockSub, MockCS):
        from platform.features.billing.subscription.subscription.infrastructure.repositories import DjangoSubscriptionRepository
        from platform.features.billing.subscription.subscription.models import Subscription as RealSub

        MockSub.DoesNotExist = RealSub.DoesNotExist
        MockSub.objects.get.side_effect = RealSub.DoesNotExist

        result = DjangoSubscriptionRepository().activate_plan(uuid.uuid4(), uuid.uuid4())

        self.assertIsNone(result)
        MockCS.objects.create.assert_not_called()


# ── CancelSubscriptionUseCase: business rules ─────────────────────────────────

class TestCancelBusinessRules(TestCase):
    """
    On cancellation:
    1. The subscription status changes from ACTIVE to CANCELLED.
    2. It is NOT deleted — access continues until end_date.
    3. If there is no active subscription, returns None.
    """

    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    def test_cancellation_changes_status_to_cancelled(self, MockCS):
        from platform.features.billing.subscription.subscription.infrastructure.repositories import DjangoSubscriptionRepository

        cs = MagicMock()
        cs.id = uuid.uuid4()
        cs.status = 'ACTIVE'
        cs.start_date = _NOW
        cs.end_date = _30_DAYS
        cs.subscription.id = uuid.uuid4()
        cs.subscription.name = 'Standard Plan'
        MockCS.Status.ACTIVE = 'ACTIVE'
        MockCS.Status.CLOSED = 'CLOSED'
        MockCS.Status.CANCELLED = 'CANCELLED'
        MockCS.objects.filter.return_value.select_related.return_value \
            .order_by.return_value.first.return_value = cs

        DjangoSubscriptionRepository().cancel(uuid.uuid4())

        self.assertEqual(cs.status, 'CANCELLED')
        cs.save.assert_called_once()

    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    def test_cancellation_without_active_subscription_returns_none(self, MockCS):
        from platform.features.billing.subscription.subscription.infrastructure.repositories import DjangoSubscriptionRepository

        MockCS.Status.ACTIVE = 'ACTIVE'
        MockCS.objects.filter.return_value.select_related.return_value \
            .order_by.return_value.first.return_value = None

        result = DjangoSubscriptionRepository().cancel(uuid.uuid4())

        self.assertIsNone(result)

    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    def test_cancellation_does_not_delete_subscription(self, MockCS):
        from platform.features.billing.subscription.subscription.infrastructure.repositories import DjangoSubscriptionRepository

        cs = MagicMock()
        cs.id = uuid.uuid4()
        cs.status = 'ACTIVE'
        cs.start_date = _NOW
        cs.end_date = _30_DAYS
        cs.subscription.id = uuid.uuid4()
        cs.subscription.name = 'Standard Plan'
        MockCS.Status.ACTIVE = 'ACTIVE'
        MockCS.Status.CLOSED = 'CLOSED'
        MockCS.Status.CANCELLED = 'CANCELLED'
        MockCS.objects.filter.return_value.select_related.return_value \
            .order_by.return_value.first.return_value = cs

        DjangoSubscriptionRepository().cancel(uuid.uuid4())

        cs.delete.assert_not_called()
        cs.save.assert_called_once()


# ── ReactivateSubscriptionUseCase: business rules ─────────────────────────────

class TestReactivateBusinessRules(TestCase):
    """
    On reactivation:
    1. Can only reactivate if the subscription has not expired (end_date > now).
    2. Status changes from CANCELLED to ACTIVE.
    3. If expired, returns None.
    """

    @patch('django.utils.timezone')
    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    def test_reactivation_succeeds_when_not_expired(self, MockCS, mock_tz):
        from platform.features.billing.subscription.subscription.infrastructure.repositories import DjangoSubscriptionRepository

        mock_tz.now.return_value = _NOW
        cs = MagicMock()
        cs.id = uuid.uuid4()
        cs.status = 'CANCELLED'
        cs.start_date = _NOW
        cs.end_date = _30_DAYS
        cs.subscription.id = uuid.uuid4()
        cs.subscription.name = 'Pro Plan'
        MockCS.Status.CANCELLED = 'CANCELLED'
        MockCS.Status.ACTIVE = 'ACTIVE'
        MockCS.objects.filter.return_value.select_related.return_value \
            .order_by.return_value.first.return_value = cs

        DjangoSubscriptionRepository().reactivate(uuid.uuid4())

        self.assertEqual(cs.status, 'ACTIVE')
        cs.save.assert_called_once()

    @patch('django.utils.timezone')
    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    def test_reactivation_fails_when_subscription_is_expired(self, MockCS, mock_tz):
        from platform.features.billing.subscription.subscription.infrastructure.repositories import DjangoSubscriptionRepository

        mock_tz.now.return_value = _NOW
        MockCS.Status.CANCELLED = 'CANCELLED'
        MockCS.objects.filter.return_value.select_related.return_value \
            .order_by.return_value.first.return_value = None

        result = DjangoSubscriptionRepository().reactivate(uuid.uuid4())

        self.assertIsNone(result)

    @patch('django.utils.timezone')
    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    def test_reactivation_filters_by_end_date_greater_than_now(self, MockCS, mock_tz):
        from platform.features.billing.subscription.subscription.infrastructure.repositories import DjangoSubscriptionRepository

        mock_tz.now.return_value = _NOW
        MockCS.Status.CANCELLED = 'CANCELLED'
        MockCS.objects.filter.return_value.select_related.return_value \
            .order_by.return_value.first.return_value = None

        company_id = uuid.uuid4()
        DjangoSubscriptionRepository().reactivate(company_id)

        MockCS.objects.filter.assert_called_with(
            company_id=company_id,
            status='CANCELLED',
            end_date__gt=_NOW,
        )

    @patch('django.utils.timezone')
    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    def test_reactivation_takes_most_recent_when_multiple_cancelled(self, MockCS, mock_tz):
        from platform.features.billing.subscription.subscription.infrastructure.repositories import DjangoSubscriptionRepository

        mock_tz.now.return_value = _NOW
        cs = MagicMock()
        cs.id = uuid.uuid4()
        cs.start_date = _NOW
        cs.end_date = _30_DAYS
        cs.subscription.id = uuid.uuid4()
        cs.subscription.name = 'Pro Plan'
        MockCS.Status.CANCELLED = 'CANCELLED'
        MockCS.Status.ACTIVE = 'ACTIVE'
        order_mock = MockCS.objects.filter.return_value.select_related \
            .return_value.order_by
        order_mock.return_value.first.return_value = cs

        DjangoSubscriptionRepository().reactivate(uuid.uuid4())

        order_mock.assert_called_with('-start_date')


# ── Subscription isolation between tenants ─────────────────────────────────────

class TestSubscriptionIsolationBetweenTenants(TestCase):
    """
    Upgrade/cancel/reactivate operations use company_id to filter.
    Two companies cannot affect each other's subscriptions.
    """

    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    def test_cancel_filters_by_company_id(self, MockCS):
        from platform.features.billing.subscription.subscription.infrastructure.repositories import DjangoSubscriptionRepository

        company_a_id = uuid.uuid4()
        MockCS.Status.ACTIVE = 'ACTIVE'
        MockCS.objects.filter.return_value.select_related.return_value \
            .order_by.return_value.first.return_value = None

        DjangoSubscriptionRepository().cancel(company_a_id)

        MockCS.objects.filter.assert_called_with(
            company_id=company_a_id,
            status='ACTIVE',
        )

    @patch('django.utils.timezone')
    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    @patch('platform.features.billing.subscription.subscription.infrastructure.repositories.Subscription')
    def test_upgrade_assigns_new_subscription_to_correct_company(self, MockSub, MockCS, mock_tz):
        from platform.features.billing.subscription.subscription.infrastructure.repositories import DjangoSubscriptionRepository

        mock_tz.now.return_value = _NOW
        sub = MagicMock()
        sub.id = uuid.uuid4()
        sub.name = 'Pro Plan'
        sub.price = Decimal('49.99')
        MockSub.objects.get.return_value = sub
        MockCS.Status.ACTIVE = 'ACTIVE'
        MockCS.Status.CLOSED = 'CLOSED'
        MockCS.Status.CANCELLED = 'CANCELLED'
        new_cs = MagicMock()
        new_cs.id = uuid.uuid4()
        new_cs.status = 'ACTIVE'
        MockCS.objects.create.return_value = new_cs
        _prepare_activate_mocks(MockCS, new_cs, sub)

        target_company_id = uuid.uuid4()
        DjangoSubscriptionRepository().activate_plan(target_company_id, uuid.uuid4())

        kwargs = MockCS.objects.create.call_args.kwargs
        self.assertEqual(kwargs['company_id'], target_company_id)


class TestExpireDue(TestCase):
    """ACTIVE + past vigencia + no pending + auto_renew off → expired."""

    @patch('django.utils.timezone')
    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    def test_expire_due_updates_matching_rows(self, MockCS, mock_tz):
        from platform.features.billing.subscription.subscription.infrastructure.repositories import (
            DjangoSubscriptionRepository,
        )

        mock_tz.now.return_value = _NOW
        company_id = uuid.uuid4()
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.values_list.return_value = [company_id]
        qs.update.return_value = 1
        MockCS.objects.filter.return_value = qs
        MockCS.Status.ACTIVE = 'active'
        MockCS.Status.EXPIRED = 'expired'

        updated = DjangoSubscriptionRepository().expire_due()

        self.assertEqual(updated, 1)
        MockCS.objects.filter.assert_called_with(
            status='active',
            end_date__lte=_NOW,
            pending_subscription__isnull=True,
            auto_renew=False,
        )
        qs.update.assert_called_with(status='expired')

    @patch('django.utils.timezone')
    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    def test_expire_due_for_company_filters_that_company(self, MockCS, mock_tz):
        from platform.features.billing.subscription.subscription.infrastructure.repositories import (
            DjangoSubscriptionRepository,
        )

        mock_tz.now.return_value = _NOW
        company_id = uuid.uuid4()
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.values_list.return_value = [company_id]
        qs.update.return_value = 1
        MockCS.objects.filter.return_value = qs
        MockCS.Status.ACTIVE = 'active'
        MockCS.Status.EXPIRED = 'expired'

        updated = DjangoSubscriptionRepository().expire_due(company_id)

        self.assertEqual(updated, 1)
        qs.filter.assert_called_with(company_id=company_id)
        qs.update.assert_called_with(status='expired')


class TestActivatePlanEvents(TestCase):
    """activate_plan publishes PeriodClosed then PeriodIssued (best-effort bus)."""

    def _wire(self, MockSub, MockCS, mock_tz, *, closed_ids=()):
        mock_tz.now.return_value = _NOW
        sub = MagicMock()
        sub.id = uuid.uuid4()
        sub.name = 'Pro Plan'
        sub.price = Decimal('99.99')
        MockSub.objects.get.return_value = sub
        MockCS.Status.ACTIVE = 'active'
        MockCS.Status.CLOSED = 'closed'
        new_cs = MagicMock()
        new_cs.id = uuid.uuid4()
        new_cs.status = 'active'
        MockCS.objects.create.return_value = new_cs
        _prepare_activate_mocks(MockCS, new_cs, sub)
        MockCS.objects.filter.return_value.values_list.return_value = list(closed_ids)
        return sub, new_cs

    @patch('platform.features.billing.subscription.subscription.domain.events.publish')
    @patch('django.utils.timezone')
    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    @patch('platform.features.billing.subscription.subscription.infrastructure.repositories.Subscription')
    def test_first_activation_publishes_issued_only(self, MockSub, MockCS, mock_tz, mock_publish):
        from platform.features.billing.subscription.subscription.infrastructure.repositories import (
            DjangoSubscriptionRepository,
        )
        sub, new_cs = self._wire(MockSub, MockCS, mock_tz)
        company_id = uuid.uuid4()
        result = DjangoSubscriptionRepository().activate_plan(company_id, sub.id)

        self.assertEqual(mock_publish.call_count, 1)
        event = mock_publish.call_args.args[0]
        self.assertIsInstance(event, PeriodIssued)
        self.assertEqual(event.company_id, company_id)
        self.assertEqual(event.period_id, new_cs.id)
        self.assertEqual(event.subscription_id, sub.id)
        self.assertIsNone(event.charge_id)
        self.assertEqual(event.closed_period_ids, [])
        self.assertEqual(result.end_date, '01/07/2025')
        self.assertEqual(result.status, 'active')

    @patch('platform.features.billing.subscription.subscription.domain.events.publish')
    @patch('django.utils.timezone')
    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    @patch('platform.features.billing.subscription.subscription.infrastructure.repositories.Subscription')
    def test_renew_publishes_closed_then_issued_with_charge(
        self, MockSub, MockCS, mock_tz, mock_publish,
    ):
        from platform.features.billing.subscription.subscription.infrastructure.repositories import (
            DjangoSubscriptionRepository,
        )
        closed_id = uuid.uuid4()
        charge_id = uuid.uuid4()
        sub, new_cs = self._wire(MockSub, MockCS, mock_tz, closed_ids=[closed_id])
        company_id = uuid.uuid4()
        DjangoSubscriptionRepository().activate_plan(
            company_id, sub.id, charge_id=charge_id,
        )

        events = [c.args[0] for c in mock_publish.call_args_list]
        self.assertEqual(len(events), 2)
        self.assertIsInstance(events[0], PeriodClosed)
        self.assertEqual(events[0].period_id, closed_id)
        self.assertEqual(events[0].company_id, company_id)
        self.assertIsInstance(events[1], PeriodIssued)
        self.assertEqual(events[1].charge_id, charge_id)
        self.assertEqual(events[1].closed_period_ids, [closed_id])
        self.assertEqual(events[1].period_id, new_cs.id)
        MockCS.objects.filter.return_value.update.assert_called_with(status='closed')

    @patch('platform.features.billing.subscription.subscription.domain.events.publish')
    @patch('django.utils.timezone')
    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    @patch('platform.features.billing.subscription.subscription.infrastructure.repositories.Subscription')
    def test_renew_without_charge_publishes_closed_then_issued(
        self, MockSub, MockCS, mock_tz, mock_publish,
    ):
        from platform.features.billing.subscription.subscription.infrastructure.repositories import (
            DjangoSubscriptionRepository,
        )
        closed_id = uuid.uuid4()
        sub, new_cs = self._wire(MockSub, MockCS, mock_tz, closed_ids=[closed_id])
        company_id = uuid.uuid4()
        DjangoSubscriptionRepository().activate_plan(company_id, sub.id)

        events = [c.args[0] for c in mock_publish.call_args_list]
        self.assertEqual(len(events), 2)
        self.assertIsInstance(events[0], PeriodClosed)
        self.assertIsInstance(events[1], PeriodIssued)
        self.assertIsNone(events[1].charge_id)
        self.assertEqual(events[1].closed_period_ids, [closed_id])
        self.assertEqual(events[1].period_id, new_cs.id)


class TestGetPendingChange(TestCase):
    """Django repo returns PendingChangeSchema (interval included), never a raw dict."""

    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    def test_returns_none_when_no_pending(self, MockCS):
        from platform.features.billing.subscription.subscription.infrastructure.repositories import (
            DjangoSubscriptionRepository,
        )
        MockCS.Status.ACTIVE = 'active'
        MockCS.objects.filter.return_value.select_related.return_value \
            .order_by.return_value.first.return_value = None
        company_id = uuid.uuid4()
        self.assertIsNone(DjangoSubscriptionRepository().get_pending_change(company_id))
        MockCS.objects.filter.assert_called_once_with(
            company_id=company_id,
            status='active',
            pending_subscription__isnull=False,
        )

    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    def test_returns_schema_with_pending_interval(self, MockCS):
        from platform.features.billing.subscription.subscription.domain.schemas import PendingChangeSchema
        from platform.features.billing.subscription.subscription.infrastructure.repositories import (
            DjangoSubscriptionRepository,
        )
        MockCS.Status.ACTIVE = 'active'
        cs = MagicMock()
        cs.subscription.name = 'Pro'
        cs.pending_subscription.name = 'Std'
        cs.end_date = _NOW
        cs.pending_billing_interval = 'yearly'
        cs.billing_interval = 'monthly'
        MockCS.objects.filter.return_value.select_related.return_value \
            .order_by.return_value.first.return_value = cs

        result = DjangoSubscriptionRepository().get_pending_change(uuid.uuid4())

        self.assertIsInstance(result, PendingChangeSchema)
        self.assertEqual(result.type, 'downgrade')
        self.assertEqual(result.from_plan, 'Pro')
        self.assertEqual(result.to_plan, 'Std')
        self.assertEqual(result.activates_on, _NOW)
        self.assertEqual(result.billing_interval, 'yearly')

    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    def test_falls_back_to_active_interval_when_pending_interval_missing(self, MockCS):
        from platform.features.billing.subscription.subscription.infrastructure.repositories import (
            DjangoSubscriptionRepository,
        )
        MockCS.Status.ACTIVE = 'active'
        cs = MagicMock()
        cs.subscription.name = 'Pro'
        cs.pending_subscription.name = 'Std'
        cs.end_date = _NOW
        cs.pending_billing_interval = None
        cs.billing_interval = 'monthly'
        MockCS.objects.filter.return_value.select_related.return_value \
            .order_by.return_value.first.return_value = cs

        result = DjangoSubscriptionRepository().get_pending_change(uuid.uuid4())
        self.assertEqual(result.billing_interval, 'monthly')


