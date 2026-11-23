"""Shared list envelope for admin billing/geography catalogs."""

from __future__ import annotations

from core.decorators.response import wrap_response
from core.query import PaginatedQuery


def catalog_list_response(query: PaginatedQuery, items: list, *, total: int | None = None):
    """Return full array when unpaginated; otherwise page envelope.

    Callers that paginate in SQL pass ``total`` and already-sliced ``items``.
    When ``total`` is omitted, falls back to in-memory slice (small catalogs).
    """
    dumped = [
        row.model_dump(mode='json') if hasattr(row, 'model_dump') else row
        for row in items
    ]
    if query.unpaginated:
        return wrap_response(dumped)
    page_size = query.page_size or 1
    if total is None:
        total = len(dumped)
        page_items = dumped[query.offset: query.offset + page_size]
    else:
        page_items = dumped
    return wrap_response({
        'items': page_items,
        'total': total,
        'page': query.page,
        'page_size': query.page_size,
        'total_pages': (total + page_size - 1) // page_size if page_size else 1,
    })
