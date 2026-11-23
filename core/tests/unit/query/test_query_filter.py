"""Unit tests for core.query QueryFilter / QueryParam."""

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase

import pytest

from core.query import (
    PATTERN_CODE,
    PATTERN_TEXT,
    PaginatedQuery,
    QueryFilter,
    QueryParam,
    validated_query,
)
from core.validators import ValidationCode
from django.utils.timezone import is_aware


pytestmark = pytest.mark.unit


class ProductsQuery(QueryFilter):
    name = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    status = QueryParam(coerce=str, choices=['active', 'inactive'])
    min_price = QueryParam(coerce=float, min_value=0)


class CatalogQuery(QueryFilter):
    ALLOW_UNPAGINATED = True
    q = QueryParam(coerce=str, max_length=100, pattern=PATTERN_TEXT)
    is_active = QueryParam(coerce=bool)
    amount = QueryParam(coerce=Decimal, min_value=0)
    on = QueryParam(coerce=date)
    at = QueryParam(coerce=datetime)
    code = QueryParam(coerce=str, max_length=40, pattern=PATTERN_CODE)


class DateRangeQuery(QueryFilter):
    DATE_RANGES = (('from', 'to'),)

    from_date = QueryParam(name='from', coerce=datetime)
    to_date = QueryParam(name='to', coerce=datetime)


class TestQueryParamDeclaration(TestCase):
    def test_str_requires_max_length(self):
        with self.assertRaises(TypeError):
            QueryParam(coerce=str, pattern=PATTERN_TEXT)

    def test_str_requires_choices_or_pattern(self):
        with self.assertRaises(TypeError):
            QueryParam(coerce=str, max_length=10)

    def test_uuid_derives_max_length(self):
        p = QueryParam(coerce=str, is_uuid=True)
        self.assertEqual(p.max_length, 36)

    def test_choices_derive_max_length(self):
        p = QueryParam(coerce=str, choices=['a', 'longer'])
        self.assertEqual(p.max_length, 6)

    def test_coerce_required(self):
        with self.assertRaises(TypeError):
            QueryParam(max_length=10, pattern=PATTERN_TEXT)  # type: ignore[call-arg]


class TestQueryFilter(TestCase):
    def test_pagination_defaults(self):
        qf = ProductsQuery({})
        ok, errors = qf.validate()
        self.assertTrue(ok, msg=errors)
        query = qf.to_query()
        self.assertEqual(query.page, 0)
        self.assertEqual(query.page_size, 10)
        self.assertFalse(query.unpaginated)
        self.assertEqual(query.filters, {})

    def test_filters_and_pagination(self):
        qf = ProductsQuery({
            'page': '1',
            'page_size': '25',
            'name': 'bolt',
            'status': 'active',
            'min_price': '10.5',
        })
        ok, errors = qf.validate()
        self.assertTrue(ok, msg=errors)
        query = qf.to_query()
        self.assertEqual(query.page, 1)
        self.assertEqual(query.page_size, 25)
        self.assertEqual(query.filters['name'], 'bolt')
        self.assertEqual(query.filters['status'], 'active')
        self.assertEqual(query.filters['min_price'], 10.5)

    def test_invalid_choice(self):
        qf = ProductsQuery({'status': 'archived'})
        ok, errors = qf.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].code, ValidationCode.INVALID_CHOICE)

    def test_invalid_page(self):
        qf = ProductsQuery({'page': '-1'})
        ok, errors = qf.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'page')

    def test_page_size_over_max_rejected(self):
        qf = ProductsQuery({'page_size': '9999'})
        ok, errors = qf.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'page_size')
        self.assertEqual(errors[0].code, ValidationCode.MAX_VALUE)

    def test_unknown_param_rejected(self):
        qf = ProductsQuery({'foo': 'bar'})
        ok, errors = qf.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].code, ValidationCode.UNKNOWN_FIELD)
        self.assertEqual(errors[0].field, 'foo')

    def test_catalog_unpaginated_when_no_page(self):
        qf = CatalogQuery({'q': 'x'})
        ok, errors = qf.validate()
        self.assertTrue(ok, msg=errors)
        query = qf.to_query()
        self.assertTrue(query.unpaginated)
        self.assertEqual(query.page_size, 0)
        self.assertEqual(query.filters['q'], 'x')

    def test_catalog_paginated_when_page_sent(self):
        qf = CatalogQuery({'page': '0', 'page_size': '20', 'q': 'x'})
        ok, errors = qf.validate()
        self.assertTrue(ok, msg=errors)
        query = qf.to_query()
        self.assertFalse(query.unpaginated)
        self.assertEqual(query.page_size, 20)

    def test_bool_coerce(self):
        for raw, expected in (('true', True), ('1', True), ('yes', True),
                              ('false', False), ('0', False), ('no', False)):
            qf = CatalogQuery({'is_active': raw})
            ok, errors = qf.validate()
            self.assertTrue(ok, msg=errors)
            self.assertIs(qf.to_query().filters['is_active'], expected)

    def test_bool_invalid(self):
        qf = CatalogQuery({'is_active': 'maybe'})
        ok, errors = qf.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].code, ValidationCode.INVALID_TYPE)

    def test_decimal_coerce(self):
        qf = CatalogQuery({'amount': '12.50'})
        ok, errors = qf.validate()
        self.assertTrue(ok, msg=errors)
        self.assertEqual(qf.to_query().filters['amount'], Decimal('12.50'))

    def test_date_and_datetime_coerce(self):
        qf = CatalogQuery({'on': '2024-03-15', 'at': '2024-03-15T12:30:00'})
        ok, errors = qf.validate()
        self.assertTrue(ok, msg=errors)
        f = qf.to_query().filters
        self.assertEqual(f['on'], date(2024, 3, 15))
        self.assertEqual(f['at'].replace(tzinfo=None), datetime(2024, 3, 15, 12, 30, 0))
        self.assertTrue(is_aware(f['at']))
        self.assertEqual(f['at'].tzinfo, dt_timezone.utc)

    def test_datetime_offset_is_utc_instant(self):
        qf = CatalogQuery({'at': '2024-03-15T12:30:00-05:00'})
        ok, errors = qf.validate()
        self.assertTrue(ok, msg=errors)
        self.assertEqual(
            qf.to_query().filters['at'],
            datetime(2024, 3, 15, 17, 30, tzinfo=dt_timezone.utc),
        )

    def test_datetime_zulu_is_utc_instant(self):
        qf = CatalogQuery({'at': '2024-03-15T12:30:00Z'})
        ok, errors = qf.validate()
        self.assertTrue(ok, msg=errors)
        self.assertEqual(
            qf.to_query().filters['at'],
            datetime(2024, 3, 15, 12, 30, tzinfo=dt_timezone.utc),
        )

    def test_invalid_calendar_date_returns_validation_error(self):
        qf = CatalogQuery({'on': '2024-13-40'})
        ok, errors = qf.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'on')
        self.assertEqual(errors[0].code, ValidationCode.INVALID_TYPE)

    def test_date_rejects_datetime_value(self):
        qf = CatalogQuery({'on': '2024-03-15T12:30:00Z'})
        ok, errors = qf.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].code, ValidationCode.INVALID_TYPE)

    def test_datetime_rejects_date_only(self):
        qf = CatalogQuery({'at': '2024-03-15'})
        ok, errors = qf.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].code, ValidationCode.INVALID_TYPE)

    def test_inverted_date_range_rejected(self):
        qf = DateRangeQuery({
            'from': '2024-03-16T12:30:00Z',
            'to': '2024-03-15T12:30:00Z',
        })
        ok, errors = qf.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'to')
        self.assertEqual(errors[0].code, ValidationCode.MIN_VALUE)

    def test_pattern(self):
        ok, _ = CatalogQuery({'code': 'ABC'}).validate()
        self.assertTrue(ok)
        ok, errors = CatalogQuery({'code': 'abc!'}).validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].code, ValidationCode.INVALID_PATTERN)

    def test_parse_success(self):
        query, err = ProductsQuery({'status': 'active'}).parse()
        self.assertIsNone(err)
        self.assertEqual(query.filters['status'], 'active')

    def test_parse_error(self):
        query, err = ProductsQuery({'status': 'nope'}).parse()
        self.assertIsNone(query)
        self.assertEqual(err.status_code, 400)


class TestValidatedQueryDecorator(TestCase):
    def test_injects_validated_query_and_preserves_route_kwargs(self):
        class View:
            @validated_query(ProductsQuery)
            def get(self, request, resource_id, *, query: PaginatedQuery):
                return {
                    'resource_id': resource_id,
                    'status': query.filters['status'],
                }

        result = View().get(
            SimpleNamespace(query_params={'status': 'active'}),
            resource_id='resource-1',
        )
        self.assertEqual(result, {'resource_id': 'resource-1', 'status': 'active'})

    def test_returns_validation_response_without_calling_view(self):
        called = False

        class View:
            @validated_query(ProductsQuery)
            def get(self, request, *, query: PaginatedQuery):
                nonlocal called
                called = True
                return {'status': query.filters['status']}

        response = View().get(SimpleNamespace(query_params={'status': 'invalid'}))
        self.assertFalse(called)
        self.assertEqual(response.status_code, 400)


class RequiredQuery(QueryFilter):
    ALLOW_UNPAGINATED = True
    key = QueryParam(coerce=str, max_length=20, pattern=PATTERN_CODE, required=True)
    tag = QueryParam(coerce=str, max_length=20, pattern=PATTERN_CODE)


@pytest.mark.parametrize('params', [{}, {'key': ''}, {'key': '   '}])
def test_required_param_missing_or_blank_is_rejected(params):
    ok, errors = RequiredQuery(params).validate()
    assert not ok
    assert [(e.field, e.code) for e in errors] == [('key', ValidationCode.REQUIRED)]


def test_required_param_present_is_coerced_and_optional_stays_absent():
    ok, errors = RequiredQuery({'key': 'ABC'}).validate()
    assert ok and errors == []
    assert RequiredQuery({'key': 'ABC'}).parse()[0].filters == {'key': 'ABC'}


class EdgeQuery(QueryFilter):
    email = QueryParam(coerce=str, is_email=True)
    ref = QueryParam(coerce=str, is_uuid=True)
    code = QueryParam(coerce=str, max_length=5, min_length=2, pattern=PATTERN_CODE)
    count = QueryParam(coerce=int, min_value=1, max_value=10)
    amount = QueryParam(coerce=Decimal)


def test_param_declaration_edges():
    with pytest.raises(TypeError):
        QueryParam(coerce=list)
    assert QueryParam(coerce=str, is_email=True).max_length == 254
    assert QueryParam(coerce=int, name='n').validate('x')[0].code == ValidationCode.INVALID_TYPE


@pytest.mark.parametrize('params, field, code', [
    ({'email': 'no-email'}, 'email', ValidationCode.INVALID_EMAIL),
    ({'ref': 'not-a-uuid'}, 'ref', ValidationCode.INVALID_UUID),
    ({'code': 'ABCDEFG'}, 'code', ValidationCode.MAX_LENGTH),
    ({'code': 'A'}, 'code', ValidationCode.MIN_LENGTH),
    ({'count': '11'}, 'count', ValidationCode.MAX_VALUE),
    ({'count': '0'}, 'count', ValidationCode.MIN_VALUE),
    ({'count': 'tres'}, 'count', ValidationCode.INVALID_TYPE),
    ({'amount': 'abc'}, 'amount', ValidationCode.INVALID_TYPE),
    ({'page': '-1'}, 'page', ValidationCode.INVALID_TYPE),
    ({'page_size': 'x'}, 'page_size', ValidationCode.INVALID_TYPE),
    ({'page_size': '0'}, 'page_size', ValidationCode.INVALID_TYPE),
])
def test_validation_errors(params, field, code):
    ok, errors = EdgeQuery(params).validate()
    assert not ok
    assert (errors[0].field, errors[0].code) == (field, code)


def test_paginated_query_limit():
    query = PaginatedQuery(page=2, page_size=25, filters={})
    assert (query.offset, query.limit) == (50, 25)
