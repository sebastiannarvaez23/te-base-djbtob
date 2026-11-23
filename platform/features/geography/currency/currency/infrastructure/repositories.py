from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Q

from core.errors import AppErrorCode, ConflictException, NotFoundException, ValidationAppException

from platform.features.geography.location.location.models import Country

from ..domain.interfaces import ICurrencyRepository
from ..domain.schemas import (
    AllowedCurrencySchema,
    CountryCurrencySchema,
    CreateCountryCurrencySchema,
    CreateCurrencySchema,
    CurrencySchema,
    UpdateCountryCurrencySchema,
    UpdateCurrencySchema,
    UpsertCurrencySeedSchema,
)
from ..models import CountryCurrency, Currency


def _currency_schema(obj: Currency) -> CurrencySchema:
    return CurrencySchema(
        id=obj.id,
        code=obj.code,
        name=obj.name,
        decimal_places=obj.decimal_places,
        is_active=obj.is_active,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


def _link_schema(obj: CountryCurrency) -> CountryCurrencySchema:
    currency = getattr(obj, 'currency', None)
    country = getattr(obj, 'country', None)
    return CountryCurrencySchema(
        id=obj.id,
        country_id=obj.country_id,
        country_code=getattr(country, 'code', '') if country else '',
        currency_id=obj.currency_id,
        currency_code=getattr(currency, 'code', '') if currency else '',
        currency_name=getattr(currency, 'name', '') if currency else '',
        decimal_places=getattr(currency, 'decimal_places', 2) if currency else 2,
        is_default=obj.is_default,
        is_active=obj.is_active,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


class DjangoCurrencyRepository(ICurrencyRepository):

    def _currencies_qs(self, filters: Optional[dict] = None):
        qs = Currency.objects.all()
        filters = filters or {}
        if filters.get('q'):
            q = filters['q']
            qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q))
        if filters.get('code'):
            qs = qs.filter(code__iexact=filters['code'])
        if filters.get('is_active') is not None:
            qs = qs.filter(is_active=filters['is_active'])
        return qs.order_by('code')

    def list_currencies(self, *, filters: Optional[dict] = None) -> List[CurrencySchema]:
        return [_currency_schema(row) for row in self._currencies_qs(filters)]

    def get_currency(self, currency_id: UUID) -> Optional[CurrencySchema]:
        try:
            return _currency_schema(Currency.objects.get(id=currency_id))
        except Currency.DoesNotExist:
            return None

    def get_currency_by_code(self, code: str) -> Optional[CurrencySchema]:
        try:
            return _currency_schema(Currency.objects.get(code=code.strip().upper()))
        except Currency.DoesNotExist:
            return None

    def create_currency(self, data: CreateCurrencySchema) -> CurrencySchema:
        try:
            row = Currency.objects.create(
                code=data.code,
                name=data.name,
                decimal_places=data.decimal_places,
                is_active=data.is_active,
            )
        except IntegrityError as exc:
            raise ConflictException(AppErrorCode.GEO_CURRENCY_DUPLICATE) from exc
        return _currency_schema(row)

    def update_currency(
        self, currency_id: UUID, data: UpdateCurrencySchema,
    ) -> Optional[CurrencySchema]:
        try:
            row = Currency.objects.get(id=currency_id)
        except Currency.DoesNotExist:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        row.save()
        return _currency_schema(row)

    def delete_currency(self, currency_id: UUID) -> bool:
        if not Currency.objects.filter(id=currency_id).exists():
            return False
        if CountryCurrency.objects.filter(currency_id=currency_id).exists():
            raise ConflictException(AppErrorCode.GEO_CURRENCY_IN_USE)
        deleted, _ = Currency.objects.filter(id=currency_id).delete()
        return deleted > 0

    def upsert_currency_by_code(
        self, data: UpsertCurrencySeedSchema,
    ) -> tuple[CurrencySchema, bool]:
        row, created = Currency.objects.update_or_create(
            code=data.code,
            defaults={
                'name': data.name,
                'decimal_places': data.decimal_places,
                'is_active': True,
            },
        )
        return _currency_schema(row), created

    def _links_qs(self, *, country_id: Optional[UUID] = None, filters: Optional[dict] = None):
        qs = CountryCurrency.objects.select_related('country', 'currency')
        if country_id is not None:
            qs = qs.filter(country_id=country_id)
        filters = filters or {}
        if filters.get('is_active') is not None:
            qs = qs.filter(is_active=filters['is_active'])
        if filters.get('is_default') is not None:
            qs = qs.filter(is_default=filters['is_default'])
        if filters.get('currency_code'):
            qs = qs.filter(currency__code__iexact=filters['currency_code'])
        return qs.order_by('currency__code')

    def list_country_currencies(
        self, *, country_id: Optional[UUID] = None, filters: Optional[dict] = None,
    ) -> List[CountryCurrencySchema]:
        return [_link_schema(row) for row in self._links_qs(country_id=country_id, filters=filters)]

    def list_allowed_by_country_code(
        self, country_code: str, *, active_only: bool = True,
    ) -> List[AllowedCurrencySchema]:
        code = country_code.strip().upper()
        qs = CountryCurrency.objects.select_related('currency', 'country').filter(
            country__code=code,
        )
        if active_only:
            qs = qs.filter(is_active=True, currency__is_active=True, country__is_active=True)
        return [
            AllowedCurrencySchema(
                code=row.currency.code,
                name=row.currency.name,
                decimal_places=row.currency.decimal_places,
                is_default=row.is_default,
            )
            for row in qs.order_by('-is_default', 'currency__code')
        ]

    def get_country_currency(self, link_id: UUID) -> Optional[CountryCurrencySchema]:
        try:
            row = CountryCurrency.objects.select_related('country', 'currency').get(id=link_id)
        except CountryCurrency.DoesNotExist:
            return None
        return _link_schema(row)

    def create_country_currency(self, data: CreateCountryCurrencySchema) -> CountryCurrencySchema:
        if not Country.objects.filter(id=data.country_id).exists():
            raise NotFoundException(AppErrorCode.GEO_COUNTRY_NOT_FOUND)
        currency = Currency.objects.filter(id=data.currency_id).first()
        if currency is None:
            raise NotFoundException(AppErrorCode.GEO_CURRENCY_NOT_FOUND)
        if not currency.is_active:
            raise ValidationAppException(AppErrorCode.GEO_CURRENCY_INACTIVE)
        try:
            with transaction.atomic():
                if data.is_default:
                    self.clear_default_for_country(data.country_id)
                row = CountryCurrency.objects.create(
                    country_id=data.country_id,
                    currency_id=data.currency_id,
                    is_default=data.is_default,
                    is_active=data.is_active,
                )
        except IntegrityError as exc:
            raise ConflictException(AppErrorCode.GEO_COUNTRY_CURRENCY_DUPLICATE) from exc
        row = CountryCurrency.objects.select_related('country', 'currency').get(id=row.id)
        return _link_schema(row)

    def update_country_currency(
        self, link_id: UUID, data: UpdateCountryCurrencySchema,
    ) -> Optional[CountryCurrencySchema]:
        try:
            row = CountryCurrency.objects.select_related('country', 'currency').get(id=link_id)
        except CountryCurrency.DoesNotExist:
            return None
        payload = data.model_dump(exclude_unset=True)
        with transaction.atomic():
            if payload.get('is_default') is True:
                self.clear_default_for_country(row.country_id, except_id=row.id)
            for key, value in payload.items():
                setattr(row, key, value)
            row.save()
        row.refresh_from_db()
        row = CountryCurrency.objects.select_related('country', 'currency').get(id=row.id)
        return _link_schema(row)

    def delete_country_currency(self, link_id: UUID) -> bool:
        deleted, _ = CountryCurrency.objects.filter(id=link_id).delete()
        return deleted > 0

    def clear_default_for_country(
        self, country_id: UUID, *, except_id: Optional[UUID] = None,
    ) -> None:
        qs = CountryCurrency.objects.filter(country_id=country_id, is_default=True)
        if except_id is not None:
            qs = qs.exclude(id=except_id)
        qs.update(is_default=False)

    def country_exists(self, country_id: UUID) -> bool:
        return Country.objects.filter(id=country_id).exists()

    def get_country_id_by_code(self, country_code: str) -> Optional[UUID]:
        try:
            return Country.objects.only('id').get(code=country_code.strip().upper()).id
        except Country.DoesNotExist:
            return None
