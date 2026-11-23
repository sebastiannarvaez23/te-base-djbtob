"""benefit_manager.py — preview and eligibility helpers."""

from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase

import pytest

from core.errors import AppErrorCode, AppException
from platform.features.billing.commerce.promotion.application.benefit_manager import (
    assert_plan_eligible,
    build_benefit_window,
    compute_preview,
)
from platform.features.billing.commerce.promotion.models import PromotionVoucher

pytestmark = pytest.mark.unit


def _sub(price, name='Plan', sub_id=None):
    return SimpleNamespace(
        id=sub_id or __import__('uuid').uuid4(),
        name=name,
        price=Decimal(str(price)),
    )


def _voucher(**kwargs):
    defaults = dict(
        voucher_type=PromotionVoucher.VoucherType.GIFT,
        benefit_months=3,
        discount_percent=Decimal('20'),
        discount_duration_months=1,
        subscriptions=MagicMockSubscriptionSet([kwargs.pop('_sub_id', None)]),
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class MagicMockSubscriptionSet:
    def __init__(self, ids):
        self._ids = [i for i in ids if i]

    def values_list(self, field, flat=False):
        return self._ids


class TestComputePreview(TestCase):

    def test_gift_preview_zero_final(self):
        sub = _sub(100, 'Pro')
        voucher = _voucher(benefit_months=3, _sub_id=sub.id)
        original, final, discount, msg = compute_preview(voucher, sub)
        self.assertEqual(final, Decimal('0'))
        self.assertEqual(discount, Decimal('100'))
        self.assertIn('3 mes', msg)

    def test_discount_preview(self):
        sub = _sub(100, 'Pro')
        voucher = _voucher(
            voucher_type=PromotionVoucher.VoucherType.DISCOUNT,
            discount_percent=Decimal('20'),
            _sub_id=sub.id,
        )
        original, final, discount, _ = compute_preview(voucher, sub)
        self.assertEqual(final, Decimal('80.00'))
        self.assertEqual(discount, Decimal('20.00'))

    def test_discount_preview_on_yearly_cycle(self):
        sub = _sub(100, 'Pro')
        voucher = _voucher(
            voucher_type=PromotionVoucher.VoucherType.DISCOUNT,
            discount_percent=Decimal('20'),
            _sub_id=sub.id,
        )
        original, final, discount, _ = compute_preview(voucher, sub, billing_interval='yearly')
        self.assertEqual(original, Decimal('1020.00'))
        self.assertEqual(final, Decimal('816.00'))
        self.assertEqual(discount, Decimal('204.00'))


class TestAssertPlanEligible(TestCase):

    def test_plan_not_in_list_raises(self):
        sub = _sub(50, 'Basic')
        voucher = _voucher(_sub_id=__import__('uuid').uuid4())
        with self.assertRaises(AppException) as ctx:
            assert_plan_eligible(voucher, sub, current_sub=None)
        self.assertEqual(ctx.exception.code, AppErrorCode.PROMO_PLAN_INELIGIBLE)

    def test_downgrade_blocked(self):
        pro = _sub(100, 'Pro')
        basic = _sub(50, 'Basic')
        voucher = _voucher(_sub_id=basic.id)
        with self.assertRaises(AppException) as ctx:
            assert_plan_eligible(voucher, basic, current_sub=pro)
        self.assertEqual(ctx.exception.code, AppErrorCode.PROMO_PLAN_INELIGIBLE)


class TestBuildBenefitWindow(TestCase):

    def test_window_spans_months(self):
        from datetime import datetime
        start = datetime(2026, 1, 15, 10, 0, 0)
        s, e = build_benefit_window(months=3, start=start)
        self.assertEqual(s, start)
        self.assertEqual(e.month, 4)
