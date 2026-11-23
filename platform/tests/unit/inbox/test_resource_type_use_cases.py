"""Tests de los casos de uso de tipos de recurso compartible."""

import uuid
from unittest.mock import MagicMock

import pytest

from core.errors.exceptions import ConflictException, NotFoundException

from platform.features.communication.messaging.inbox.application.use_cases import (
    CreateResourceTypeUseCase,
    ListResourceTypesUseCase,
    UpdateResourceTypeUseCase,
)
from platform.features.communication.messaging.inbox.domain.schemas import (
    CreateResourceTypeSchema,
    ResourceTypeSchema,
    UpdateResourceTypeSchema,
)

pytestmark = pytest.mark.unit


def _schema(**kw):
    base = dict(id=uuid.uuid4(), code='PICKING', label='Picking', icon='', route_template='', is_active=True)
    base.update(kw)
    return ResourceTypeSchema(**base)


def test_create_rejects_duplicate_code():
    repo = MagicMock()
    repo.get_by_code.return_value = _schema()
    with pytest.raises(ConflictException):
        CreateResourceTypeUseCase(repo).execute(CreateResourceTypeSchema(code='PICKING', label='Picking'))
    repo.create.assert_not_called()


def test_create_persists_when_code_is_new():
    repo = MagicMock()
    repo.get_by_code.return_value = None
    repo.create.return_value = _schema()
    result = CreateResourceTypeUseCase(repo).execute(CreateResourceTypeSchema(code='PICKING', label='Picking'))
    repo.create.assert_called_once()
    assert result.code == 'PICKING'


def test_update_raises_when_missing():
    repo = MagicMock()
    repo.update.return_value = None
    with pytest.raises(NotFoundException):
        UpdateResourceTypeUseCase(repo).execute('NOPE', UpdateResourceTypeSchema(is_active=False))


def test_list_delegates_only_active_flag():
    repo = MagicMock()
    repo.list.return_value = [_schema()]
    ListResourceTypesUseCase(repo).execute(only_active=True)
    repo.list.assert_called_once_with(only_active=True)
