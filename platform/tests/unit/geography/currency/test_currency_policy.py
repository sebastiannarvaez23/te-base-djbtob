"""Unit tests — DjangoCountryCurrencyPolicy (billing charge currency)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from core.errors import AppErrorCode, ValidationAppException
from platform.features.billing.commerce.payments.integration.adapters.country_currency_policy import (
    DjangoCountryCurrencyPolicy,
)
from platform.features.geography.currency.currency.domain.schemas import AllowedCurrencySchema

pytestmark = pytest.mark.unit


def _allowed(*codes, default='COP'):
    return [
        AllowedCurrencySchema(
            code=code,
            name=code,
            is_default=(code == default),
        )
        for code in codes
    ]


class TestDjangoCountryCurrencyPolicy:
    def setup_method(self):
        self.repo = MagicMock()
        self.policy = DjangoCountryCurrencyPolicy(currency_repo=self.repo)
        self.company_id = uuid4()

    @patch(
        'platform.features.billing.commerce.payments.integration.adapters'
        '.country_currency_policy._company_country_code',
        return_value='CO',
    )
    def test_allows_cop_and_usd_for_co(self, _country):
        self.repo.list_allowed_by_country_code.return_value = _allowed(
            'COP', 'USD', default='COP',
        )
        assert self.policy.assert_charge_currency(
            company_id=self.company_id, currency='usd',
        ) == 'USD'
        assert self.policy.assert_charge_currency(
            company_id=self.company_id, currency='COP',
        ) == 'COP'

    @patch(
        'platform.features.billing.commerce.payments.integration.adapters'
        '.country_currency_policy._company_country_code',
        return_value='CO',
    )
    def test_falls_back_to_country_default_when_preferred_not_linked(self, _country):
        self.repo.list_allowed_by_country_code.return_value = _allowed(
            'COP', 'USD', default='COP',
        )
        assert self.policy.assert_charge_currency(
            company_id=self.company_id, currency='EUR',
        ) == 'COP'

    @patch(
        'platform.features.billing.commerce.payments.integration.adapters'
        '.country_currency_policy._company_country_code',
        return_value='CO',
    )
    def test_empty_allow_list_uses_catalog_active(self, _country):
        self.repo.list_allowed_by_country_code.return_value = []
        self.repo.get_currency_by_code.return_value = SimpleNamespace(
            code='USD', is_active=True,
        )
        assert self.policy.assert_charge_currency(
            company_id=self.company_id, currency='USD',
        ) == 'USD'

    @patch(
        'platform.features.billing.commerce.payments.integration.adapters'
        '.country_currency_policy._company_country_code',
        return_value='CO',
    )
    def test_default_is_country_default(self, _country):
        self.repo.list_allowed_by_country_code.return_value = _allowed(
            'COP', 'USD', default='COP',
        )
        assert self.policy.default_currency_for_company(self.company_id) == 'COP'
        assert self.policy.assert_charge_currency(
            company_id=self.company_id, currency='',
        ) == 'COP'

    @patch(
        'platform.features.billing.commerce.payments.integration.adapters'
        '.country_currency_policy._company_country_code',
        return_value=None,
    )
    @patch(
        'platform.features.billing.commerce.payments.integration.adapters'
        '.country_currency_policy._fallback_currency',
        return_value='USD',
    )
    def test_fallback_when_company_has_no_geo(self, _fallback, _country):
        self.repo.get_currency_by_code.return_value = SimpleNamespace(
            code='USD', is_active=True,
        )
        assert self.policy.default_currency_for_company(self.company_id) == 'USD'
        assert self.policy.assert_charge_currency(
            company_id=self.company_id, currency='USD',
        ) == 'USD'

    def test_refund_mismatch(self):
        with pytest.raises(ValidationAppException) as exc:
            self.policy.assert_refund_currency(charge_currency='COP', currency='USD')
        assert exc.value.code == AppErrorCode.PAY_CURRENCY_MISMATCH

    def test_refund_match(self):
        assert self.policy.assert_refund_currency(
            charge_currency='cop', currency='COP',
        ) == 'COP'
