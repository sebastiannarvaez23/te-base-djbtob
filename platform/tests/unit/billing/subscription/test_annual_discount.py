"""Unit tests for the annual-discount platform parameter use cases."""
from decimal import Decimal
from unittest import TestCase
from unittest.mock import MagicMock

import pytest

from platform.features.billing.subscription.subscription.application.use_cases import (
    GetAnnualDiscountUseCase,
    UpdateAnnualDiscountUseCase,
)

pytestmark = pytest.mark.unit


class TestGetAnnualDiscountUseCase(TestCase):

    def test_returns_repository_value(self):
        repo = MagicMock()
        repo.get_annual_discount_percent.return_value = Decimal('20.00')
        result = GetAnnualDiscountUseCase(repo).execute()
        self.assertEqual(result.annual_discount_percent, Decimal('20.00'))

    def test_happy_path_default_fifteen(self):
        repo = MagicMock()
        repo.get_annual_discount_percent.return_value = Decimal('15')
        result = GetAnnualDiscountUseCase(repo).execute()
        self.assertEqual(result.annual_discount_percent, Decimal('15'))


class TestUpdateAnnualDiscountUseCase(TestCase):

    def test_persists_and_returns_saved_value(self):
        repo = MagicMock()
        repo.update_annual_discount_percent.return_value = Decimal('12.50')
        result = UpdateAnnualDiscountUseCase(repo).execute(Decimal('12.50'))
        repo.update_annual_discount_percent.assert_called_once_with(Decimal('12.50'))
        self.assertEqual(result.annual_discount_percent, Decimal('12.50'))

    def test_zero_is_a_valid_parameter(self):
        repo = MagicMock()
        repo.update_annual_discount_percent.return_value = Decimal('0.00')
        result = UpdateAnnualDiscountUseCase(repo).execute(Decimal('0'))
        self.assertEqual(result.annual_discount_percent, Decimal('0.00'))
