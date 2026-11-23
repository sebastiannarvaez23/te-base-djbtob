"""Unit tests for tabular_extractor.

Coercion (`extract_cell`) is tested directly — no external deps.
JSONPath resolution (`resolve_rows`) is gated on jsonpath_ng being
installed; skipped otherwise so contributors without optional tabular
deps can still run the suite.
"""
from datetime import date, datetime
from decimal import Decimal

import pytest

from platform.features.documents.document_template.document_template.domain.format_configs import TabularColumn
from platform.features.documents.document_template.document_template.infrastructure.renderers.tabular_extractor import (
    extract_cell,
    extract_rows,
)


def _col(key, fmt='text', label=None):
    return TabularColumn(key=key, label=label or key, format=fmt)


# ── Cell-level coercion ──────────────────────────────────────────────────────


class TestExtractCellText:

    def test_string_passthrough(self):
        assert extract_cell({'name': 'Ana'}, _col('name')) == 'Ana'

    def test_missing_key_returns_none(self):
        assert extract_cell({'other': 1}, _col('name')) is None

    def test_empty_string_returns_none(self):
        assert extract_cell({'name': ''}, _col('name')) is None

    def test_non_dict_row_returns_none(self):
        assert extract_cell('not-a-dict', _col('name')) is None

    def test_number_in_text_column_stringifies(self):
        assert extract_cell({'name': 42}, _col('name')) == '42'


class TestExtractCellNumber:

    def test_int_passthrough(self):
        assert extract_cell({'qty': 5}, _col('qty', 'number')) == 5

    def test_float_passthrough(self):
        assert extract_cell({'qty': 3.14}, _col('qty', 'number')) == 3.14

    def test_string_int_parsed(self):
        assert extract_cell({'qty': '7'}, _col('qty', 'number')) == 7

    def test_string_float_parsed_with_dot(self):
        assert extract_cell({'qty': '3.14'}, _col('qty', 'number')) == 3.14

    def test_string_float_with_comma_locale_handled(self):
        assert extract_cell({'qty': '3,14'}, _col('qty', 'number')) == 3.14

    def test_unparseable_falls_back_to_text(self):
        assert extract_cell({'qty': 'abc'}, _col('qty', 'number')) == 'abc'


class TestExtractCellCurrency:

    def test_decimal_passthrough(self):
        out = extract_cell({'price': Decimal('99.99')}, _col('price', 'currency'))
        assert out == Decimal('99.99')

    def test_string_becomes_decimal(self):
        out = extract_cell({'price': '199.50'}, _col('price', 'currency'))
        assert out == Decimal('199.50')

    def test_comma_decimal_separator_handled(self):
        out = extract_cell({'price': '199,50'}, _col('price', 'currency'))
        assert out == Decimal('199.50')


class TestExtractCellDate:

    def test_date_passthrough(self):
        d = date(2026, 5, 30)
        assert extract_cell({'d': d}, _col('d', 'date')) == d

    def test_datetime_passthrough(self):
        dt = datetime(2026, 5, 30, 12, 0, 0)
        assert extract_cell({'d': dt}, _col('d', 'date')) == dt

    def test_iso_date_string_parsed(self):
        assert extract_cell({'d': '2026-05-30'}, _col('d', 'date')) == date(2026, 5, 30)

    def test_iso_datetime_string_parsed(self):
        out = extract_cell({'d': '2026-05-30T12:34:56'}, _col('d', 'date'))
        assert isinstance(out, datetime)
        assert out.year == 2026 and out.month == 5 and out.day == 30

    def test_z_suffix_treated_as_utc(self):
        out = extract_cell({'d': '2026-05-30T12:00:00Z'}, _col('d', 'date'))
        assert isinstance(out, datetime)

    def test_unparseable_passes_through_as_string(self):
        assert extract_cell({'d': 'tomorrow'}, _col('d', 'date')) == 'tomorrow'


# ── Multi-row extraction ─────────────────────────────────────────────────────


class TestExtractRows:

    def test_returns_2d_matrix_in_column_order(self):
        rows = [
            {'name': 'A', 'qty': 1, 'price': '10'},
            {'name': 'B', 'qty': 2, 'price': '20'},
        ]
        columns = [_col('name'), _col('qty', 'number'), _col('price', 'currency')]
        out = extract_rows(rows, columns)
        assert out == [
            ['A', 1, Decimal('10')],
            ['B', 2, Decimal('20')],
        ]

    def test_empty_rows_returns_empty_matrix(self):
        assert extract_rows([], [_col('name')]) == []


# ── JSONPath (optional) ──────────────────────────────────────────────────────


class TestResolveRows:
    """Run only when jsonpath_ng is installed (production dep)."""

    def setup_method(self):
        pytest.importorskip('jsonpath_ng')
        from platform.features.documents.document_template.document_template.infrastructure.renderers.tabular_extractor import (
            resolve_rows,
        )
        self._resolve = resolve_rows

    def test_resolves_simple_array_path(self):
        data = {'items': [{'a': 1}, {'a': 2}]}
        assert self._resolve('$.items', data) == [{'a': 1}, {'a': 2}]

    def test_no_match_returns_empty(self):
        assert self._resolve('$.missing', {'items': []}) == []

    def test_invalid_path_raises_app_error(self):
        from core.errors import AppErrorCode, AppException
        with pytest.raises(AppException) as exc_info:
            self._resolve('not[a-valid-path', {})
        assert exc_info.value.code == AppErrorCode.DOC_FORMAT_CONFIG_INVALID
