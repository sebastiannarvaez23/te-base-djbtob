"""Unit tests — currency catalog and country–currency links."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from core.errors import AppErrorCode, NotFoundException
from platform.features.geography.currency.currency.application.use_cases import (
    CreateCountryCurrencyUseCase,
    CreateCurrencyUseCase,
    DeleteCurrencyUseCase,
    GetCurrencyUseCase,
    ListAllowedCurrenciesUseCase,
    ListCountryCurrenciesUseCase,
    ListCurrenciesUseCase,
    UpdateCountryCurrencyUseCase,
    UpdateCurrencyUseCase,
)
from platform.features.geography.currency.currency.domain.schemas import (
    AllowedCurrencySchema,
    CountryCurrencySchema,
    CreateCountryCurrencySchema,
    CreateCurrencySchema,
    CurrencySchema,
    UpdateCountryCurrencySchema,
    UpdateCurrencySchema,
)

pytestmark = pytest.mark.unit


def _currency(**overrides) -> CurrencySchema:
    base = dict(
        id=uuid4(),
        code='USD',
        name='US Dollar',
        decimal_places=2,
        is_active=True,
    )
    base.update(overrides)
    return CurrencySchema(**base)


def _link(**overrides) -> CountryCurrencySchema:
    base = dict(
        id=uuid4(),
        country_id=uuid4(),
        country_code='CO',
        currency_id=uuid4(),
        currency_code='COP',
        currency_name='Colombian Peso',
        decimal_places=2,
        is_default=True,
        is_active=True,
    )
    base.update(overrides)
    return CountryCurrencySchema(**base)


class TestCurrencyUseCases:
    def test_create_normalizes_code(self):
        repo = MagicMock()
        created = _currency(code='USD')
        repo.create_currency.return_value = created
        with patch(
            'platform.features.geography.currency.currency.application.use_cases.invalidate_cache',
        ) as inv:
            result = CreateCurrencyUseCase(repo).execute(
                CreateCurrencySchema(code='usd', name='US Dollar'),
            )
        assert result.code == 'USD'
        inv.assert_called()

    def test_get_not_found(self):
        repo = MagicMock()
        repo.get_currency.return_value = None
        with pytest.raises(NotFoundException) as exc:
            GetCurrencyUseCase(repo).execute(uuid4())
        assert exc.value.code == AppErrorCode.GEO_CURRENCY_NOT_FOUND

    def test_list_returns_all(self):
        repo = MagicMock()
        repo.list_currencies.return_value = [_currency(), _currency(code='COP', name='Peso')]
        # Unique filter key avoids Redis HIT from prior runs of the cached use case.
        filters = {'is_active': True, 'q': f'test-{uuid4().hex[:8]}'}
        items = ListCurrenciesUseCase(repo).execute(filters=filters)
        assert len(items) == 2
        repo.list_currencies.assert_called_once_with(filters=filters)

    def test_update_not_found(self):
        repo = MagicMock()
        repo.update_currency.return_value = None
        with pytest.raises(NotFoundException):
            UpdateCurrencyUseCase(repo).execute(
                uuid4(), UpdateCurrencySchema(name='X'),
            )

    def test_delete_not_found(self):
        repo = MagicMock()
        repo.delete_currency.return_value = False
        with pytest.raises(NotFoundException):
            DeleteCurrencyUseCase(repo).execute(uuid4())


class TestCountryCurrencyUseCases:
    def test_list_requires_country(self):
        repo = MagicMock()
        repo.country_exists.return_value = False
        with pytest.raises(NotFoundException) as exc:
            ListCountryCurrenciesUseCase(repo).execute(uuid4())
        assert exc.value.code == AppErrorCode.GEO_COUNTRY_NOT_FOUND

    @patch(
        'core.cache.decorators._cache',
    )
    def test_list_allowed_by_country_code(self, cache_factory):
        cache = MagicMock()
        cache.get.return_value = None
        cache_factory.return_value = cache
        repo = MagicMock()
        repo.get_country_id_by_code.return_value = uuid4()
        repo.list_allowed_by_country_code.return_value = [
            AllowedCurrencySchema(code='COP', name='Peso', is_default=True),
            AllowedCurrencySchema(code='USD', name='Dollar', is_default=False),
        ]
        items = ListAllowedCurrenciesUseCase(repo).execute('co')
        assert [i.code for i in items] == ['COP', 'USD']
        repo.list_allowed_by_country_code.assert_called_once_with('CO', active_only=True)

    def test_list_allowed_unknown_country(self):
        repo = MagicMock()
        repo.get_country_id_by_code.return_value = None
        with pytest.raises(NotFoundException) as exc:
            ListAllowedCurrenciesUseCase(repo).execute('ZZ')
        assert exc.value.code == AppErrorCode.GEO_COUNTRY_NOT_FOUND

    def test_create_link_invalidates_cache(self):
        repo = MagicMock()
        link = _link()
        repo.create_country_currency.return_value = link
        with patch(
            'platform.features.geography.currency.currency.application.use_cases.invalidate_cache',
        ) as inv:
            CreateCountryCurrencyUseCase(repo).execute(
                CreateCountryCurrencySchema(
                    country_id=link.country_id,
                    currency_id=link.currency_id,
                    is_default=True,
                ),
            )
        inv.assert_called()

    def test_update_link_not_found(self):
        repo = MagicMock()
        repo.update_country_currency.return_value = None
        with pytest.raises(NotFoundException) as exc:
            UpdateCountryCurrencyUseCase(repo).execute(
                uuid4(), UpdateCountryCurrencySchema(is_default=True),
            )
        assert exc.value.code == AppErrorCode.GEO_COUNTRY_CURRENCY_NOT_FOUND
