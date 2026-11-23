"""Use cases — currency catalog and country–currency links."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from core.cache import invalidate_cache, use_case_cache
from core.errors import AppErrorCode, NotFoundException, ValidationAppException
from core.trace import trace_layer

from ..domain.interfaces import ICurrencyRepository
from ..domain.schemas import (
    AllowedCurrencySchema,
    CountryCurrencySchema,
    CreateCountryCurrencySchema,
    CreateCurrencySchema,
    CurrencySchema,
    UpdateCountryCurrencySchema,
    UpdateCurrencySchema,
)

CACHE_PREFIX = 'geo_currency'


def _bump_currency_cache() -> None:
    invalidate_cache(f'{CACHE_PREFIX}:*')


class ListCurrenciesUseCase:
    def __init__(self, repository: ICurrencyRepository):
        self.repository = repository

    @trace_layer('application')
    @use_case_cache(prefix=CACHE_PREFIX)
    def execute(self, *, filters: Optional[dict] = None) -> List[CurrencySchema]:
        return self.repository.list_currencies(filters=filters)


class GetCurrencyUseCase:
    def __init__(self, repository: ICurrencyRepository):
        self.repository = repository

    @trace_layer('application')
    @use_case_cache(prefix=CACHE_PREFIX)
    def execute(self, currency_id: UUID) -> CurrencySchema:
        row = self.repository.get_currency(currency_id)
        if not row:
            raise NotFoundException(AppErrorCode.GEO_CURRENCY_NOT_FOUND)
        return row


class CreateCurrencyUseCase:
    def __init__(self, repository: ICurrencyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateCurrencySchema) -> CurrencySchema:
        row = self.repository.create_currency(data)
        _bump_currency_cache()
        return row


class UpdateCurrencyUseCase:
    def __init__(self, repository: ICurrencyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, currency_id: UUID, data: UpdateCurrencySchema) -> CurrencySchema:
        row = self.repository.update_currency(currency_id, data)
        if not row:
            raise NotFoundException(AppErrorCode.GEO_CURRENCY_NOT_FOUND)
        _bump_currency_cache()
        return row


class DeleteCurrencyUseCase:
    def __init__(self, repository: ICurrencyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, currency_id: UUID) -> None:
        if not self.repository.delete_currency(currency_id):
            raise NotFoundException(AppErrorCode.GEO_CURRENCY_NOT_FOUND)
        _bump_currency_cache()


class ListCountryCurrenciesUseCase:
    def __init__(self, repository: ICurrencyRepository):
        self.repository = repository

    @trace_layer('application')
    @use_case_cache(prefix=CACHE_PREFIX)
    def execute(
        self,
        country_id: UUID,
        *,
        filters: Optional[dict] = None,
    ) -> List[CountryCurrencySchema]:
        if not self.repository.country_exists(country_id):
            raise NotFoundException(AppErrorCode.GEO_COUNTRY_NOT_FOUND)
        return self.repository.list_country_currencies(country_id=country_id, filters=filters)


class ListAllowedCurrenciesUseCase:
    """Active currencies allowed for a country ISO code (charge UI)."""

    def __init__(self, repository: ICurrencyRepository):
        self.repository = repository

    @trace_layer('application')
    @use_case_cache(prefix=CACHE_PREFIX)
    def execute(self, country_code: str) -> List[AllowedCurrencySchema]:
        code = (country_code or '').strip().upper()
        if len(code) != 2:
            raise ValidationAppException(AppErrorCode.GEO_CURRENCY_NOT_ALLOWED)
        if self.repository.get_country_id_by_code(code) is None:
            raise NotFoundException(AppErrorCode.GEO_COUNTRY_NOT_FOUND)
        return self.repository.list_allowed_by_country_code(code, active_only=True)


class CreateCountryCurrencyUseCase:
    def __init__(self, repository: ICurrencyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateCountryCurrencySchema) -> CountryCurrencySchema:
        row = self.repository.create_country_currency(data)
        _bump_currency_cache()
        return row


class UpdateCountryCurrencyUseCase:
    def __init__(self, repository: ICurrencyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self, link_id: UUID, data: UpdateCountryCurrencySchema,
    ) -> CountryCurrencySchema:
        row = self.repository.update_country_currency(link_id, data)
        if not row:
            raise NotFoundException(AppErrorCode.GEO_COUNTRY_CURRENCY_NOT_FOUND)
        _bump_currency_cache()
        return row


class DeleteCountryCurrencyUseCase:
    def __init__(self, repository: ICurrencyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, link_id: UUID) -> None:
        if not self.repository.delete_country_currency(link_id):
            raise NotFoundException(AppErrorCode.GEO_COUNTRY_CURRENCY_NOT_FOUND)
        _bump_currency_cache()
