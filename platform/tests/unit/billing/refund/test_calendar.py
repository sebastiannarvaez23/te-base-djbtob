import pytest

from datetime import date

from platform.features.billing.commerce.refund.domain.calendar import add_business_days

pytestmark = pytest.mark.unit


def test_skips_weekends():
    # Friday 2026-08-21 + 1 business day → Monday 24
    assert add_business_days(date(2026, 8, 21), 1) == date(2026, 8, 24)


def test_zero_days_stays():
    assert add_business_days(date(2026, 8, 26), 0) == date(2026, 8, 26)


def test_thirty_business_days_from_wednesday():
    # 2026-08-26 Wed + 30 weekdays
    assert add_business_days(date(2026, 8, 26), 30) == date(2026, 10, 7)
