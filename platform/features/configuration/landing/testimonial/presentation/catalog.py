from collections.abc import Sequence

from pydantic import BaseModel

from core.decorators.response import wrap_response
from core.query import PaginatedQuery


def catalog_response(
    query: PaginatedQuery,
    items: Sequence[BaseModel],
    *,
    total: int | None = None,
):
    dumped = [item.model_dump(mode='json') for item in items]
    if query.unpaginated:
        return wrap_response(dumped)
    if total is None:
        total = len(dumped)
        page_items = dumped[query.offset: query.offset + query.page_size]
    else:
        page_items = dumped
    return wrap_response({
        'items': page_items,
        'total': total,
        'page': query.page,
        'page_size': query.page_size,
        'total_pages': (
            (total + query.page_size - 1) // query.page_size if query.page_size else 1
        ),
    })
