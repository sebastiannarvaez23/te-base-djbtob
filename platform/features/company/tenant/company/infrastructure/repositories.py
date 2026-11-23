from typing import Optional, List
from uuid import UUID

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.errors import AppErrorCode, ConflictException

from core.query.core import PaginatedQuery, PaginatedResult
from platform.features.billing.subscription.subscription.domain.billing_cycle import (
    MONTHLY,
    charge_amount,
    normalize_billing_interval,
    period_delta,
)
from platform.features.billing.subscription.subscription.infrastructure.billing_settings import (
    live_annual_discount_percent,
)
from platform.features.billing.subscription.subscription.models import Subscription, CompanySubscription
from ..domain.interfaces import ICompanyRepository
from ..domain.location import company_location_codes, company_location_labels
from ..domain.schemas import (
    CompanyDetailSchema,
    CompanyDetailSubscriptionSchema,
    CompanySchema,
    CompanyListItemSchema,
    CompanySubscriptionSchema,
    CreateCompanySchema,
    UpdateCompanySchema,
)
from ..domain.lifecycle import DIRECTORY_HIDDEN_LIFECYCLES
from ..models import Company, Domain

_GEO_SELECT = 'geo_city__department__country'


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _lifecycle_fields(company: Company) -> dict:
    return dict(
        lifecycle=company.lifecycle or 'ACTIVE',
        closed_at=_iso(company.closed_at),
        purge_after=_iso(company.purge_after),
        closed_reason=company.closed_reason or '',
        legal_hold=bool(company.legal_hold),
        legal_hold_reason=company.legal_hold_reason or '',
        export_attested_at=_iso(company.export_attested_at),
        export_object_key=company.export_object_key or '',
    )


def _company_schema(company: Company) -> CompanySchema:
    country, state, city = company_location_labels(company)
    return CompanySchema(
        id=company.id,
        schema_name=company.schema_name,
        nit=company.nit,
        name=company.name,
        address=company.address,
        geo_city_id=company.geo_city_id,
        country=country,
        state=state,
        city=city,
        **_lifecycle_fields(company),
    )


def _to_list_item(company: Company, sub: Optional[CompanySubscription]) -> CompanyListItemSchema:
    subscription = None
    if sub:
        subscription = CompanySubscriptionSchema(
            id=str(sub.id),
            subscription_name=sub.subscription.name,
            subscription_code=sub.subscription.code,
            status=sub.status.upper(),
            start_date=sub.start_date.isoformat(),
            end_date=sub.end_date.isoformat(),
            billing_interval=sub.billing_interval or 'monthly',
        )
    country, state, city = company_location_labels(company)
    return CompanyListItemSchema(
        id=company.id,
        schema_name=company.schema_name,
        nit=company.nit,
        name=company.name,
        address=company.address,
        geo_city_id=company.geo_city_id,
        country=country,
        state=state,
        city=city,
        is_active=sub is not None and sub.status == CompanySubscription.Status.ACTIVE,
        created=str(company.created),
        subscription=subscription,
        **_lifecycle_fields(company),
    )


def _to_detail(company: Company) -> CompanyDetailSchema:
    primary_domain = (
        Domain.objects
        .filter(tenant=company, is_primary=True)
        .first()
    )
    latest_sub = (
        CompanySubscription.objects
        .filter(company=company)
        .select_related('subscription')
        .order_by('-start_date')
        .first()
    )

    subscription = None
    if latest_sub:
        subscription = CompanyDetailSubscriptionSchema(
            id=latest_sub.id,
            name=latest_sub.subscription.name,
            status=latest_sub.status,
            end_date=latest_sub.end_date.isoformat(),
            billing_interval=latest_sub.billing_interval or 'monthly',
        )

    country, state, city = company_location_labels(company)
    country_code, state_code, city_code = company_location_codes(company)
    nit = company.nit or ''
    return CompanyDetailSchema(
        id=company.id,
        schema_name=company.schema_name,
        nit=nit,
        name=company.name,
        address=company.address,
        geo_city_id=company.geo_city_id,
        country=country,
        state=state,
        city=city,
        country_code=country_code,
        state_code=state_code,
        city_code=city_code,
        domain=primary_domain.domain if primary_domain else None,
        created_at=company.created.isoformat() if company.created else None,
        subscription=subscription,
        is_registered=bool(nit.strip()),
        **_lifecycle_fields(company),
    )


class DjangoCompanyRepository(ICompanyRepository):

    def get_by_nit(self, nit: str) -> Optional[CompanySchema]:
        if not (nit or '').strip():
            return None
        try:
            company = Company.objects.select_related(_GEO_SELECT).get(nit=nit)
            return _company_schema(company)
        except Company.DoesNotExist:
            return None

    def get_by_id(self, company_id: UUID) -> Optional[CompanySchema]:
        try:
            company = Company.objects.select_related(_GEO_SELECT).get(id=company_id)
            return _company_schema(company)
        except Company.DoesNotExist:
            return None

    def get_by_schema_name(self, schema_name: str) -> Optional[CompanySchema]:
        if not (schema_name or '').strip():
            return None
        try:
            company = Company.objects.select_related(_GEO_SELECT).get(schema_name=schema_name)
            return _company_schema(company)
        except Company.DoesNotExist:
            return None

    def get_detail_by_nit(self, nit: str) -> Optional[CompanyDetailSchema]:
        if not (nit or '').strip():
            return None
        try:
            company = Company.objects.select_related(_GEO_SELECT).get(nit=nit)
        except Company.DoesNotExist:
            return None
        return _to_detail(company)

    def get_detail_by_id(self, company_id: UUID) -> Optional[CompanyDetailSchema]:
        try:
            company = Company.objects.select_related(_GEO_SELECT).get(id=company_id)
        except Company.DoesNotExist:
            return None
        return _to_detail(company)

    def get_all(self) -> List[CompanySchema]:
        qs = (
            Company.objects
            .select_related(_GEO_SELECT)
            .exclude(lifecycle__in=DIRECTORY_HIDDEN_LIFECYCLES)
        )
        return [_company_schema(c) for c in qs]

    @staticmethod
    def _latest_subs_qs():
        """Latest CompanySubscription per company (by start_date). PostgreSQL only."""
        return (
            CompanySubscription.objects
            .order_by('company_id', '-start_date')
            .distinct('company_id')
        )

    def get_paginated(self, query: PaginatedQuery) -> PaginatedResult:
        qs = (
            Company.objects
            .select_related(_GEO_SELECT)
            .exclude(lifecycle__in=DIRECTORY_HIDDEN_LIFECYCLES)
            .order_by('-created')
        )
        f = query.filters

        if 'name' in f:
            qs = qs.filter(name__icontains=f['name'])
        if 'nit' in f:
            qs = qs.filter(nit__icontains=f['nit'])
        if 'city' in f:
            qs = qs.filter(geo_city__name__icontains=f['city'])

        latest_sub_ids = self._latest_subs_qs().values_list('id', flat=True)

        if 'subscription' in f:
            matching_company_ids = CompanySubscription.objects.filter(
                id__in=latest_sub_ids,
                subscription__name__icontains=f['subscription'],
            ).values_list('company_id', flat=True)
            qs = qs.filter(id__in=matching_company_ids)

        if 'lifecycle' in f:
            qs = qs.filter(lifecycle=f['lifecycle'])

        if 'status' in f:
            active_company_ids = CompanySubscription.objects.filter(
                id__in=latest_sub_ids,
                status=CompanySubscription.Status.ACTIVE,
            ).values_list('company_id', flat=True)
            if f['status'] == 'active':
                qs = qs.filter(id__in=active_company_ids)
            else:
                qs = qs.exclude(id__in=active_company_ids)

        total = qs.count()
        companies = list(qs[query.offset: query.offset + query.limit])

        company_ids = [c.id for c in companies]
        latest_subs = {}
        if company_ids:
            subs = (
                CompanySubscription.objects
                .filter(company_id__in=company_ids)
                .select_related('subscription')
                .order_by('company_id', '-start_date')
            )
            for sub in subs:
                if sub.company_id not in latest_subs:
                    latest_subs[sub.company_id] = sub

        items = [_to_list_item(c, latest_subs.get(c.id)) for c in companies]
        total_pages = (total + query.page_size - 1) // query.page_size if query.page_size else 1
        return PaginatedResult(items=items, total=total, page=query.page, page_size=query.page_size, total_pages=total_pages)

    def create(self, data: CreateCompanySchema) -> CompanySchema:
        try:
            with transaction.atomic():
                company = Company.objects.create(
                    schema_name=data.schema_name,
                    nit=data.nit,
                    name=data.name,
                    address=data.address,
                    geo_city_id=data.geo_city_id,
                )
                company = Company.objects.select_related(_GEO_SELECT).get(pk=company.pk)
                domain = Domain()
                domain.domain = f"{data.schema_name}.{settings.DOMAIN_PLATFORM}"
                domain.is_primary = True
                domain.tenant = company
                domain.save()

                subscription = Subscription.objects.get(id=data.subscription_id)
                interval = normalize_billing_interval(getattr(data, 'billing_interval', None) or MONTHLY)
                now = timezone.now()
                CompanySubscription.objects.create(
                    company=company,
                    subscription=subscription,
                    start_date=now,
                    end_date=now + period_delta(interval),
                    status=CompanySubscription.Status.ACTIVE,
                    price_paid=charge_amount(
                        subscription.price,
                        interval,
                        live_annual_discount_percent(),
                    ),
                    billing_interval=interval,
                    auto_renew=True,
                )
        except IntegrityError as exc:
            if 'uniq_company_nit_when_set' in str(exc).lower():
                raise ConflictException(AppErrorCode.COMPANY_DUPLICATE_NIT) from exc
            raise

        return _company_schema(company)

    def toggle_active(self, company_id: UUID) -> Optional[CompanyListItemSchema]:
        try:
            company = Company.objects.select_related(_GEO_SELECT).get(id=company_id)
        except Company.DoesNotExist:
            return None

        latest_sub = (
            CompanySubscription.objects
            .filter(company=company)
            .select_related('subscription')
            .order_by('-start_date')
            .first()
        )
        if latest_sub:
            if latest_sub.status == CompanySubscription.Status.ACTIVE:
                latest_sub.status = CompanySubscription.Status.SUSPENDED
            else:
                latest_sub.status = CompanySubscription.Status.ACTIVE
            latest_sub.save(update_fields=['status'])

        return _to_list_item(company, latest_sub)

    def update_settings(self, company_id: UUID, data: UpdateCompanySchema) -> Optional[CompanyDetailSchema]:
        try:
            company = Company.objects.select_related(_GEO_SELECT).get(id=company_id)
        except Company.DoesNotExist:
            return None

        if data.name is not None:
            company.name = data.name
        if data.address is not None:
            company.address = data.address
        if data.nit is not None:
            current = (company.nit or '').strip()
            incoming = (data.nit or '').strip()
            if not current and incoming:
                company.nit = incoming

        try:
            with transaction.atomic():
                company.save()
        except IntegrityError as exc:
            if 'uniq_company_nit_when_set' in str(exc).lower():
                raise ConflictException(AppErrorCode.COMPANY_DUPLICATE_NIT) from exc
            raise

        company = Company.objects.select_related(_GEO_SELECT).get(pk=company.pk)
        return _to_detail(company)

    def get_orm_instance(self, nit: str) -> Optional[Company]:
        try:
            return Company.objects.select_related(_GEO_SELECT).get(nit=nit)
        except Company.DoesNotExist:
            return None
