"""
Unit tests for the pagination & query-filter system (core.query.core).

No database required — pure logic tests.
"""
from unittest import TestCase

from core.query import PATTERN_TEXT, QueryFilter, QueryParam
from core.query.core import PaginatedQuery, PaginatedResult


# ── Concrete filters for testing ─────────────────────────────────────────────

class EmptyFilter(QueryFilter):
    """No custom params — only built-in page / page_size."""
    pass


class ProductsFilter(QueryFilter):
    name   = QueryParam(coerce=str, max_length=100, pattern=PATTERN_TEXT)
    status = QueryParam(coerce=str, choices=['active', 'inactive'])
    price  = QueryParam(coerce=float, min_value=0, max_value=10000)


# ── PaginatedQuery ───────────────────────────────────────────────────────────

class TestPaginatedQuery(TestCase):

    def test_offset_is_page_times_page_size(self):
        q = PaginatedQuery(page=3, page_size=10, filters={})
        self.assertEqual(q.offset, 30)

    def test_offset_is_zero_for_first_page(self):
        q = PaginatedQuery(page=0, page_size=10, filters={})
        self.assertEqual(q.offset, 0)

    def test_limit_equals_page_size(self):
        q = PaginatedQuery(page=0, page_size=25, filters={})
        self.assertEqual(q.limit, 25)


# ── PaginatedResult ──────────────────────────────────────────────────────────

class TestPaginatedResult(TestCase):

    def test_stores_all_pagination_metadata(self):
        r = PaginatedResult(items=[1, 2, 3], total=30, page=0, page_size=10, total_pages=3)
        self.assertEqual(r.items, [1, 2, 3])
        self.assertEqual(r.total, 30)
        self.assertEqual(r.page, 0)
        self.assertEqual(r.page_size, 10)
        self.assertEqual(r.total_pages, 3)


# ── QueryFilter — default page / page_size ───────────────────────────────────

class TestQueryFilterDefaults(TestCase):

    def test_defaults_page_to_zero(self):
        qf = EmptyFilter({})
        ok, _ = qf.validate()
        self.assertTrue(ok)
        self.assertEqual(qf.to_query().page, 0)

    def test_defaults_page_size_to_ten(self):
        qf = EmptyFilter({})
        qf.validate()
        self.assertEqual(qf.to_query().page_size, 10)

    def test_accepts_explicit_page_and_page_size(self):
        qf = EmptyFilter({'page': '2', 'page_size': '20'})
        ok, _ = qf.validate()
        self.assertTrue(ok)
        q = qf.to_query()
        self.assertEqual(q.page, 2)
        self.assertEqual(q.page_size, 20)

    def test_rejects_page_size_above_max(self):
        qf = EmptyFilter({'page_size': '999'})
        ok, errors = qf.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'page_size')

    def test_rejects_negative_page(self):
        qf = EmptyFilter({'page': '-1'})
        ok, errors = qf.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'page')

    def test_rejects_non_numeric_page(self):
        qf = EmptyFilter({'page': 'abc'})
        ok, errors = qf.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'page')

    def test_rejects_zero_page_size(self):
        qf = EmptyFilter({'page_size': '0'})
        ok, errors = qf.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'page_size')

    def test_rejects_negative_page_size(self):
        qf = EmptyFilter({'page_size': '-5'})
        ok, errors = qf.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'page_size')


# ── QueryFilter — custom params ──────────────────────────────────────────────

class TestQueryFilterCustomParams(TestCase):

    def test_absent_params_not_in_filters(self):
        qf = ProductsFilter({})
        qf.validate()
        self.assertEqual(qf.to_query().filters, {})

    def test_present_params_included_in_filters(self):
        qf = ProductsFilter({'name': 'Widget', 'status': 'active'})
        ok, _ = qf.validate()
        self.assertTrue(ok)
        filters = qf.to_query().filters
        self.assertEqual(filters['name'], 'Widget')
        self.assertEqual(filters['status'], 'active')

    def test_coerces_numeric_param(self):
        qf = ProductsFilter({'price': '49.99'})
        ok, _ = qf.validate()
        self.assertTrue(ok)
        self.assertAlmostEqual(qf.to_query().filters['price'], 49.99)

    def test_rejects_invalid_choice(self):
        qf = ProductsFilter({'status': 'deleted'})
        ok, errors = qf.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'status')

    def test_rejects_string_exceeding_max_length(self):
        qf = ProductsFilter({'name': 'x' * 101})
        ok, errors = qf.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'name')

    def test_rejects_numeric_below_min_value(self):
        qf = ProductsFilter({'price': '-10'})
        ok, errors = qf.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'price')

    def test_rejects_numeric_above_max_value(self):
        qf = ProductsFilter({'price': '99999'})
        ok, errors = qf.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'price')

    def test_rejects_non_numeric_for_float_param(self):
        qf = ProductsFilter({'price': 'cheap'})
        ok, errors = qf.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'price')


# ── QueryParam — specific rules ──────────────────────────────────────────────

class TestQueryParam(TestCase):

    def test_email_param_rejects_invalid_format(self):
        p = QueryParam(coerce=str, is_email=True)
        p.name = 'email'
        errors = p.validate('not-an-email')
        self.assertTrue(len(errors) > 0)

    def test_email_param_accepts_valid_email(self):
        p = QueryParam(coerce=str, is_email=True)
        p.name = 'email'
        errors = p.validate('user@example.com')
        self.assertEqual(len(errors), 0)

    def test_uuid_param_rejects_invalid_format(self):
        p = QueryParam(coerce=str, is_uuid=True)
        p.name = 'id'
        errors = p.validate('not-a-uuid')
        self.assertTrue(len(errors) > 0)

    def test_uuid_param_accepts_valid_uuid(self):
        p = QueryParam(coerce=str, is_uuid=True)
        p.name = 'id'
        errors = p.validate('12345678-1234-5678-1234-567812345678')
        self.assertEqual(len(errors), 0)

    def test_min_length_rejects_short_string(self):
        p = QueryParam(coerce=str, max_length=100, min_length=3, pattern=PATTERN_TEXT)
        p.name = 'q'
        errors = p.validate('ab')
        self.assertTrue(len(errors) > 0)

    def test_int_coercion_rejects_non_integer(self):
        p = QueryParam(coerce=int)
        p.name = 'count'
        errors = p.validate('abc')
        self.assertTrue(len(errors) > 0)

    def test_int_coercion_accepts_valid_integer(self):
        p = QueryParam(coerce=int)
        p.name = 'count'
        errors = p.validate('42')
        self.assertEqual(len(errors), 0)


# ── QueryFilter — error_response format ──────────────────────────────────────

class TestQueryFilterErrorResponse(TestCase):

    def test_error_response_returns_400(self):
        qf = EmptyFilter({'page': 'xyz'})
        ok, errors = qf.validate()
        response = qf.error_response(errors)
        self.assertEqual(response.status_code, 400)

    def test_error_response_includes_errors_list(self):
        qf = EmptyFilter({'page': 'xyz'})
        ok, errors = qf.validate()
        response = qf.error_response(errors)
        self.assertIn('errors', response.data)
        self.assertTrue(len(response.data['errors']) > 0)
