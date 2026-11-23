"""H — Company voucher email dispatch (ports-injected, ORM-free)."""

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

import pytest

from platform.features.billing.commerce.promotion.application.voucher_emails import (
    dispatch_company_voucher_email,
)
from platform.features.billing.commerce.promotion.domain.schemas import AdminSnapshot
from platform.features.billing.commerce.promotion.models import PromotionVoucher

pytestmark = pytest.mark.unit

_THREAD = 'platform.features.billing.commerce.promotion.application.voucher_emails.threading.Thread'


class TestEmailDispatch(TestCase):

    def _voucher(self, **kwargs):
        defaults = dict(
            scope=PromotionVoucher.Scope.COMPANY,
            company_id=__import__('uuid').uuid4(),
            voucher_type=PromotionVoucher.VoucherType.GIFT,
            serial='WLGX-GFT-EMAIL01',
            benefit_months=3,
            discount_percent=None,
            discount_duration_months=1,
            redeem_valid_until=datetime(2026, 12, 31),
            notes='',
            company=SimpleNamespace(name='Acme'),
            subscriptions=MagicMock(),
        )
        defaults.update(kwargs)
        v = SimpleNamespace(**defaults)
        plan = SimpleNamespace(name='Pro', price=Decimal('100.00'))
        names = MagicMock()
        names.first.return_value = plan.name
        names.__iter__ = lambda _self: iter([plan.name])
        v.subscriptions.values_list.return_value = names
        v.subscriptions.first.return_value = plan
        return v

    def _directory(self, admin=None):
        directory = MagicMock()
        directory.admin_of.return_value = admin
        directory.company_name.return_value = 'Acme'
        return directory

    @patch(_THREAD)
    def test_h1_company_gift_sends_email(self, MockThread):
        admin = AdminSnapshot(email='admin@acme.test', first_name='Ada', last_name='Byron')
        dispatch_company_voucher_email(
            notifier=MagicMock(), directory=self._directory(admin), voucher=self._voucher(),
        )
        MockThread.assert_called_once()
        kwargs = MockThread.call_args[1]
        self.assertTrue(kwargs.get('daemon'))

    @patch(_THREAD)
    def test_h3_open_scope_skips_email(self, MockThread):
        dispatch_company_voucher_email(
            notifier=MagicMock(),
            directory=self._directory(),
            voucher=self._voucher(scope=PromotionVoucher.Scope.OPEN, company_id=None),
        )
        MockThread.assert_not_called()

    @patch(_THREAD)
    def test_h4_email_failure_does_not_raise(self, MockThread):
        admin = AdminSnapshot(email='admin@acme.test', first_name='Ada', last_name='Byron')
        instance = MagicMock()
        MockThread.return_value = instance
        dispatch_company_voucher_email(
            notifier=MagicMock(), directory=self._directory(admin), voucher=self._voucher(),
        )  # must not raise
        instance.start.assert_called_once()
