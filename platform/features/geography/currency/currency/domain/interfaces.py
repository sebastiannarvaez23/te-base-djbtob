from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from .schemas import (
    AllowedCurrencySchema,
    CountryCurrencySchema,
    CreateCountryCurrencySchema,
    CreateCurrencySchema,
    CurrencySchema,
    UpdateCountryCurrencySchema,
    UpdateCurrencySchema,
    UpsertCurrencySeedSchema,
)


class ICurrencyRepository(ABC):

    @abstractmethod
    def list_currencies(self, *, filters: Optional[dict] = None) -> List[CurrencySchema]:
        ...

    @abstractmethod
    def get_currency(self, currency_id: UUID) -> Optional[CurrencySchema]:
        ...

    @abstractmethod
    def get_currency_by_code(self, code: str) -> Optional[CurrencySchema]:
        ...

    @abstractmethod
    def create_currency(self, data: CreateCurrencySchema) -> CurrencySchema:
        ...

    @abstractmethod
    def update_currency(
        self, currency_id: UUID, data: UpdateCurrencySchema,
    ) -> Optional[CurrencySchema]:
        ...

    @abstractmethod
    def delete_currency(self, currency_id: UUID) -> bool:
        ...

    @abstractmethod
    def upsert_currency_by_code(self, data: UpsertCurrencySeedSchema) -> tuple[CurrencySchema, bool]:
        """Returns (row, created)."""
        ...

    @abstractmethod
    def list_country_currencies(
        self, *, country_id: Optional[UUID] = None, filters: Optional[dict] = None,
    ) -> List[CountryCurrencySchema]:
        ...

    @abstractmethod
    def list_allowed_by_country_code(
        self, country_code: str, *, active_only: bool = True,
    ) -> List[AllowedCurrencySchema]:
        ...

    @abstractmethod
    def get_country_currency(self, link_id: UUID) -> Optional[CountryCurrencySchema]:
        ...

    @abstractmethod
    def create_country_currency(self, data: CreateCountryCurrencySchema) -> CountryCurrencySchema:
        ...

    @abstractmethod
    def update_country_currency(
        self, link_id: UUID, data: UpdateCountryCurrencySchema,
    ) -> Optional[CountryCurrencySchema]:
        ...

    @abstractmethod
    def delete_country_currency(self, link_id: UUID) -> bool:
        ...

    @abstractmethod
    def clear_default_for_country(self, country_id: UUID, *, except_id: Optional[UUID] = None) -> None:
        ...

    @abstractmethod
    def country_exists(self, country_id: UUID) -> bool:
        ...

    @abstractmethod
    def get_country_id_by_code(self, country_code: str) -> Optional[UUID]:
        ...
