"""
Shared logic for tabular renderers (XLSX / CSV / XML).

Responsibilities:
  - Resolve `rows_path` (JSONPath) against the user data.
  - Extract per-column values from each row.
  - Format raw values according to column.format (text/number/date/currency).

The renderers themselves stay focused on their format-specific output:
  XLSX → cells with style, CSV → delimited text, XML → tagged elements.
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from core.errors import AppErrorCode, AppException

from ...domain.format_configs import TabularColumn


def resolve_rows(rows_path: str, data: dict[str, Any]) -> list[Any]:
    """Resolve `rows_path` over `data` and return the matched list.

    If the path resolves to a single non-list value, it is wrapped into
    a one-element list. If it matches nothing, returns an empty list.
    Bad JSONPath syntax raises a clear error to the consumer.
    """
    try:
        from jsonpath_ng.ext import parse as jsonpath_parse  # lazy import
    except ImportError as exc:
        raise AppException(
            AppErrorCode.DOC_RENDER_FAILED,
            override_detail=f'jsonpath-ng not installed: {exc}',
        )
    try:
        expr = jsonpath_parse(rows_path)
    except Exception as exc:
        raise AppException(
            AppErrorCode.DOC_FORMAT_CONFIG_INVALID,
            override_detail=f'Invalid rows_path "{rows_path}": {exc}',
        )

    matches = [m.value for m in expr.find(data)]

    if not matches:
        return []

    # Most useful shape: rows_path resolved to a list → use it directly.
    if len(matches) == 1 and isinstance(matches[0], list):
        return matches[0]

    # Otherwise treat each match as a row (covers $..items[*] style paths).
    return matches


def extract_cell(row: Any, column: TabularColumn) -> Any:
    """Pull `column.key` from `row` and apply format-aware coercion.

    Returns the raw Python value (int, float, str, datetime, etc.) so each
    renderer can decide its own serialization. None is returned for missing
    keys — renderers map None to their own empty representation.
    """
    if not isinstance(row, dict):
        return None

    raw = row.get(column.key)
    if raw is None or raw == '':
        return None

    fmt = (column.format or 'text').lower()

    if fmt == 'number':
        return _to_number(raw)
    if fmt == 'currency':
        return _to_decimal(raw)
    if fmt == 'date':
        return _to_date(raw)
    return _to_text(raw)


def extract_rows(rows: Iterable[Any], columns: list[TabularColumn]) -> list[list[Any]]:
    """Materialize all rows as 2D matrix in the column order given."""
    return [[extract_cell(r, c) for c in columns] for r in rows]


# ── Coercion helpers ────────────────────────────────────────────────

def _to_text(value: Any) -> str:
    return str(value)


def _to_number(value: Any):
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    try:
        s = str(value).replace(',', '.')
        if '.' in s:
            return float(s)
        return int(s)
    except (TypeError, ValueError):
        return _to_text(value)


def _to_decimal(value: Any):
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).replace(',', '.'))
    except (InvalidOperation, TypeError, ValueError):
        return _to_text(value)


def _to_date(value: Any):
    if isinstance(value, (datetime, date)):
        return value
    if not isinstance(value, str):
        return _to_text(value)
    # Try ISO-8601 first (common across APIs).
    try:
        if 'T' in value or len(value) > 10:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        return date.fromisoformat(value)
    except ValueError:
        return value  # fall back to raw string; renderer will treat as text
