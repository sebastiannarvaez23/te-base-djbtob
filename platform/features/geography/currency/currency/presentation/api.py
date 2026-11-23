"""API admin — currency master and country–currency links."""

from __future__ import annotations

from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication
from platform.features.billing.commerce._list_response import catalog_list_response

from platform.features.geography.currency.currency.application.use_cases import (
    CreateCountryCurrencyUseCase,
    CreateCurrencyUseCase,
    DeleteCountryCurrencyUseCase,
    DeleteCurrencyUseCase,
    GetCurrencyUseCase,
    ListAllowedCurrenciesUseCase,
    ListCountryCurrenciesUseCase,
    ListCurrenciesUseCase,
    UpdateCountryCurrencyUseCase,
    UpdateCurrencyUseCase,
)
from platform.features.geography.currency.currency.domain.schemas import (
    CreateCountryCurrencySchema,
    CreateCurrencySchema,
    UpdateCountryCurrencySchema,
    UpdateCurrencySchema,
)
from platform.features.geography.currency.currency.infrastructure.repositories import (
    DjangoCurrencyRepository,
)
from platform.features.geography.currency.currency.presentation.bodies import (
    CreateCountryCurrencyBody,
    CreateCurrencyBody,
    UpdateCountryCurrencyBody,
    UpdateCurrencyBody,
)
from platform.features.geography.currency.currency.presentation.queries import (
    AllowedCurrencyQuery,
    CountryCurrencyListQuery,
    CurrencyListQuery,
)


def _repo():
    return DjangoCurrencyRepository()


class CurrencyListCreateView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(CurrencyListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        items = ListCurrenciesUseCase(_repo()).execute(filters=query.filters or {})
        return catalog_list_response(query, items)

    @validated_body(CreateCurrencyBody)
    def post(self, request, *args, body: dict, **kwargs):
        if body.get('code'):
            body = {**body, 'code': str(body['code']).strip().upper()}
        result = CreateCurrencyUseCase(_repo()).execute(CreateCurrencySchema(**body))
        audit_log(request, 'Currency', result.id, 'CREATE', f'Currency created: {result.code}')
        return wrap_response(result.model_dump(mode='json'), status_code=201)


class CurrencyDetailView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        result = GetCurrencyUseCase(_repo()).execute(pk)
        return wrap_response(result.model_dump(mode='json'))

    @validated_body(UpdateCurrencyBody)
    def patch(self, request, pk, *args, body: dict, **kwargs):
        result = UpdateCurrencyUseCase(_repo()).execute(pk, UpdateCurrencySchema(**body))
        audit_log(request, 'Currency', pk, 'UPDATE', changes=body)
        return wrap_response(result.model_dump(mode='json'))

    def delete(self, request, pk, *args, **kwargs):
        DeleteCurrencyUseCase(_repo()).execute(pk)
        audit_log(request, 'Currency', pk, 'DELETE')
        return Response(status=status.HTTP_204_NO_CONTENT)


class AllowedCurrencyListView(APIView):
    """``GET /platform/currencies/allowed/?country_code=CO`` — unpaginated."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(AllowedCurrencyQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        country_code = (query.filters or {}).get('country_code') or ''
        items = ListAllowedCurrenciesUseCase(_repo()).execute(str(country_code).upper())
        # Small allow-list for charge UI — always full array.
        return wrap_response([item.model_dump(mode='json') for item in items])


class CountryCurrencyListCreateView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(CountryCurrencyListQuery)
    def get(self, request, country_id: UUID, *args, query: PaginatedQuery, **kwargs):
        items = ListCountryCurrenciesUseCase(_repo()).execute(
            country_id, filters=query.filters or {},
        )
        return catalog_list_response(query, items)

    @validated_body(CreateCountryCurrencyBody)
    def post(self, request, country_id: UUID, *args, body: dict, **kwargs):
        result = CreateCountryCurrencyUseCase(_repo()).execute(
            CreateCountryCurrencySchema(country_id=country_id, **body),
        )
        audit_log(
            request, 'CountryCurrency', result.id, 'CREATE',
            f'Link {result.country_code}/{result.currency_code}',
        )
        return wrap_response(result.model_dump(mode='json'), status_code=201)


class CountryCurrencyDetailView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(UpdateCountryCurrencyBody)
    def patch(self, request, country_id: UUID, pk: UUID, *args, body: dict, **kwargs):
        existing = _repo().get_country_currency(pk)
        if existing is None or existing.country_id != country_id:
            from core.errors import AppErrorCode, NotFoundException
            raise NotFoundException(AppErrorCode.GEO_COUNTRY_CURRENCY_NOT_FOUND)
        result = UpdateCountryCurrencyUseCase(_repo()).execute(
            pk, UpdateCountryCurrencySchema(**body),
        )
        audit_log(request, 'CountryCurrency', pk, 'UPDATE', changes=body)
        return wrap_response(result.model_dump(mode='json'))

    def delete(self, request, country_id: UUID, pk: UUID, *args, **kwargs):
        existing = _repo().get_country_currency(pk)
        if existing is None or existing.country_id != country_id:
            from core.errors import AppErrorCode, NotFoundException
            raise NotFoundException(AppErrorCode.GEO_COUNTRY_CURRENCY_NOT_FOUND)
        DeleteCountryCurrencyUseCase(_repo()).execute(pk)
        audit_log(request, 'CountryCurrency', pk, 'DELETE')
        return Response(status=status.HTTP_204_NO_CONTENT)
