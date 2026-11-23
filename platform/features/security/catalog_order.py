"""Helpers to persist catalog display order (sections / modules / features)."""
import uuid
from typing import Iterable

from django.db import transaction
from django.db.models import Case, IntegerField, Max, Value, When

from core.errors import AppErrorCode, ValidationAppException
from platform.features.security.access.functionalities.domain.categories import FUNCTIONALITY_CATEGORIES


def category_rank() -> Case:
    """Sort key that lists features by category (features → ai → api); unknown ones last."""
    return Case(
        *(When(category=category, then=Value(rank)) for rank, category in enumerate(FUNCTIONALITY_CATEGORIES)),
        default=Value(len(FUNCTIONALITY_CATEGORIES)),
        output_field=IntegerField(),
    )


def parse_uuid_ids(raw_ids: Iterable) -> list[uuid.UUID]:
    parsed: list[uuid.UUID] = []
    for raw in raw_ids:
        try:
            parsed.append(uuid.UUID(str(raw)))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail=f'Invalid id: {raw!r}.',
            ) from exc
    return parsed


def next_order(model, **filters) -> int:
    qs = model.objects.filter(**filters) if filters else model.objects.all()
    current = qs.aggregate(m=Max('order'))['m']
    return (current if current is not None else -1) + 1


def apply_order(model, ids: list[uuid.UUID], **filters) -> int:
    base = model.objects.filter(**filters) if filters else model.objects
    with transaction.atomic():
        updated = 0
        for index, pk in enumerate(ids):
            updated += base.filter(id=pk).update(order=index)
    return updated
