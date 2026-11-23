"""High-precision unit tests for the SUB_UPGRADE / SUB_DOWNGRADE context
builders — the data layer feeding the plan-change emails."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase

from platform.features.billing.subscription.subscription.application.change_emails import (
    PLATFORM_URL,
    build_downgrade_context,
    build_suspended_context,
    build_upgrade_context,
)
from platform.features.billing.commerce.invoice.application.invoice_context import SUPPORT_EMAIL


_NOW = datetime(2026, 6, 28, 9, 42, tzinfo=timezone.utc)


def _plan(name, price, features=None):
    return SimpleNamespace(id=uuid.uuid4(), name=name,
                           price=Decimal(str(price)), features=features or [])


def _admin():
    return SimpleNamespace(first_name='Ana', last_name='Gómez',
                           email='ana@acme.com', username='ana')


def _company():
    return SimpleNamespace(name='Acme S.A.S')


class TestUpgradeContext(TestCase):

    def test_maps_every_field(self):
        ctx = build_upgrade_context(
            new_plan=_plan('Enterprise', 89.99, ['users_100', 'api']),
            previous_plan=_plan('Professional', 49.99),
            admin=_admin(), company=_company(), now=_NOW,
        )
        self.assertEqual(ctx['new_plan'], 'Enterprise')
        self.assertEqual(ctx['new_price'], 89.99)
        self.assertIsInstance(ctx['new_price'], float)
        self.assertEqual(ctx['previous_plan'], 'Professional')
        self.assertEqual(ctx['user_name'], 'Ana Gómez')
        self.assertEqual(ctx['company_name'], 'Acme S.A.S')
        self.assertEqual(ctx['current_year'], 2026)
        self.assertEqual(ctx['upgrade_date'], '2026-06-28')
        self.assertEqual(ctx['platform_url'], PLATFORM_URL)
        self.assertEqual(ctx['support_email'], SUPPORT_EMAIL)
        self.assertEqual(ctx['new_features_list'], '- users_100\n- api')

    def test_no_previous_plan_yields_empty_string(self):
        ctx = build_upgrade_context(
            new_plan=_plan('Enterprise', 89.99), previous_plan=None,
            admin=_admin(), company=_company(), now=_NOW,
        )
        self.assertEqual(ctx['previous_plan'], '')

    def test_no_admin_yields_empty_user_name(self):
        ctx = build_upgrade_context(
            new_plan=_plan('Enterprise', 89.99), previous_plan=None,
            admin=None, company=_company(), now=_NOW,
        )
        self.assertEqual(ctx['user_name'], '')


class TestDowngradeContext(TestCase):

    def test_maps_every_field(self):
        ctx = build_downgrade_context(
            new_plan=_plan('Professional', 29.99),
            previous_plan=_plan('Enterprise', 89.99),
            admin=_admin(), company=_company(), now=_NOW,
        )
        self.assertEqual(ctx['new_plan'], 'Professional')
        self.assertEqual(ctx['new_price'], 29.99)
        self.assertEqual(ctx['previous_plan'], 'Enterprise')
        self.assertEqual(ctx['downgrade_date'], '2026-06-28')
        self.assertEqual(ctx['upgrade_url'], PLATFORM_URL)
        self.assertEqual(ctx['support_email'], SUPPORT_EMAIL)

    def test_removed_features_are_those_lost_in_the_new_plan(self):
        ctx = build_downgrade_context(
            new_plan=_plan('Professional', 29.99, features=['users_15', 'reports_basic']),
            previous_plan=_plan('Enterprise', 89.99,
                                features=['users_15', 'reports_basic', 'api', 'priority_support']),
            admin=_admin(), company=_company(), now=_NOW,
        )
        # only features present before but not after
        self.assertEqual(ctx['removed_features_list'], '- api\n- priority_support')

    def test_no_previous_plan_yields_empty_removed_list(self):
        ctx = build_downgrade_context(
            new_plan=_plan('Professional', 29.99, features=['x']),
            previous_plan=None, admin=_admin(), company=_company(), now=_NOW,
        )
        self.assertEqual(ctx['removed_features_list'], '')
        self.assertEqual(ctx['previous_plan'], '')


class TestSuspendedContext(TestCase):

    def test_maps_every_field(self):
        ctx = build_suspended_context(
            plan=_plan('Empresarial', 79.99), admin=_admin(), company=_company(), now=_NOW,
        )
        self.assertEqual(ctx['subscription_name'], 'Empresarial')
        self.assertEqual(ctx['total_due'], 79.99)
        self.assertIsInstance(ctx['total_due'], float)
        self.assertEqual(ctx['user_name'], 'Ana Gómez')
        self.assertEqual(ctx['company_name'], 'Acme S.A.S')
        self.assertEqual(ctx['current_year'], 2026)
        self.assertEqual(ctx['cancellation_date'], '2026-06-28')
        self.assertEqual(ctx['reactivation_url'], PLATFORM_URL)
        self.assertEqual(ctx['support_email'], SUPPORT_EMAIL)
        # billing period derived from `now` (Junio → Julio 2026)
        self.assertIn('Junio 2026', ctx['billing_period'])
        self.assertIn('Julio 2026', ctx['billing_period'])
