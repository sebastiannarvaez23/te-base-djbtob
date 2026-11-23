"""Borrado lógico: marca la fila, no la elimina."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core.models.soft_delete import SoftDeleteModel, SoftDeleteQuerySet

pytestmark = pytest.mark.unit


def _queryset() -> SoftDeleteQuerySet:
    qs = SoftDeleteQuerySet.__new__(SoftDeleteQuerySet)
    qs.model = SimpleNamespace(_meta=SimpleNamespace(label='test.Thing'))
    qs.update = MagicMock(return_value=2)
    return qs


def test_queryset_delete_marks_deleted_at():
    qs = _queryset()
    count, detail = qs.delete()
    assert count == 2
    assert detail == {'test.Thing': 2}
    assert qs.update.call_args.kwargs['deleted_at'] is not None


def test_queryset_restore_clears_deleted_at():
    qs = _queryset()
    qs.restore()
    qs.update.assert_called_once_with(deleted_at=None)


def test_instance_delete_saves_only_deleted_at():
    row = SoftDeleteModel.__new__(SoftDeleteModel)
    row.save = MagicMock()
    row.delete()
    assert row.deleted_at is not None
    assert row.is_deleted is True
    row.save.assert_called_once_with(update_fields=['deleted_at'])


def test_instance_restore_clears_the_mark():
    row = SoftDeleteModel.__new__(SoftDeleteModel)
    row.deleted_at = object()
    row.save = MagicMock()
    row.restore()
    assert row.deleted_at is None
    assert row.is_deleted is False
    row.save.assert_called_once_with(update_fields=['deleted_at'])
