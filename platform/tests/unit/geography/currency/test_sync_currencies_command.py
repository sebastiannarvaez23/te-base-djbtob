"""Unit tests — sync_currencies management command (idempotent seed)."""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from django.core.management import call_command

from platform.features.geography.currency.currency.domain.schemas import (
    CountryCurrencySchema,
    CurrencySchema,
)

pytestmark = pytest.mark.unit


def _currency(code: str) -> CurrencySchema:
    return CurrencySchema(
        id=uuid4(),
        code=code,
        name=code,
        decimal_places=2,
        is_active=True,
    )


class TestSyncCurrenciesCommand:
    @patch(
        'platform.features.geography.currency.currency.management.commands'
        '.sync_currencies.transaction.atomic',
    )
    @patch(
        'platform.features.geography.currency.currency.management.commands'
        '.sync_currencies.DjangoCurrencyRepository',
    )
    def test_creates_currencies_and_links_when_country_exists(self, Repo, atomic):
        atomic.return_value.__enter__ = MagicMock(return_value=None)
        atomic.return_value.__exit__ = MagicMock(return_value=False)
        repo = Repo.return_value
        usd = _currency('USD')
        cop = _currency('COP')
        repo.upsert_currency_by_code.side_effect = [(usd, True), (cop, True)]
        country_id = uuid4()
        repo.get_country_id_by_code.side_effect = lambda code: (
            country_id if code in ('CO', 'US') else None
        )
        repo.list_country_currencies.return_value = []
        repo.create_country_currency.side_effect = lambda data: CountryCurrencySchema(
            id=uuid4(),
            country_id=data.country_id,
            country_code='CO',
            currency_id=data.currency_id,
            currency_code='X',
            is_default=data.is_default,
            is_active=True,
        )

        out = StringIO()
        call_command('sync_currencies', stdout=out)

        assert repo.upsert_currency_by_code.call_count == 2
        assert repo.create_country_currency.call_count == 3  # CO:COP+USD, US:USD
        assert 'created=2' in out.getvalue() or 'Currencies created=2' in out.getvalue()

    @patch(
        'platform.features.geography.currency.currency.management.commands'
        '.sync_currencies.transaction.atomic',
    )
    @patch(
        'platform.features.geography.currency.currency.management.commands'
        '.sync_currencies.DjangoCurrencyRepository',
    )
    def test_skips_missing_countries_and_is_idempotent(self, Repo, atomic):
        atomic.return_value.__enter__ = MagicMock(return_value=None)
        atomic.return_value.__exit__ = MagicMock(return_value=False)
        repo = Repo.return_value
        usd = _currency('USD')
        cop = _currency('COP')
        repo.upsert_currency_by_code.side_effect = [(usd, False), (cop, False)]
        repo.get_country_id_by_code.return_value = None

        out = StringIO()
        call_command('sync_currencies', stdout=out)

        repo.create_country_currency.assert_not_called()
        assert 'Skipped country links' in out.getvalue()
