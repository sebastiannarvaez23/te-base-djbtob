"""
Unit tests for ParameterType CRUD use cases.

No database required — pure logic tests with mocked repository.
"""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock

from core.errors.exceptions import ConflictException, NotFoundException
from core.errors.codes import AppErrorCode
from platform.features.configuration.parameters.parameter_type.application.use_cases import (
    GetAllParameterTypesUseCase,
    GetParameterTypeByIdUseCase,
    CreateParameterTypeUseCase,
    UpdateParameterTypeUseCase,
    DeleteParameterTypeUseCase,
)
from platform.features.configuration.parameters.parameter_type.domain.schemas import (
    CreateParameterTypeSchema,
    ParameterTypeSchema,
    UpdateParameterTypeSchema,
)


def _ptype(**overrides) -> ParameterTypeSchema:
    defaults = dict(
        id=uuid.uuid4(),
        code='SECURITY',
        name='Security & Access',
        description='Security related parameters',
        is_active=True,
    )
    defaults.update(overrides)
    return ParameterTypeSchema(**defaults)


# ── GetAllParameterTypesUseCase ──────────────────────────────────────────────


class TestGetAllParameterTypes(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = GetAllParameterTypesUseCase(self.repo)

    def test_returns_all_types(self):
        expected = [_ptype(), _ptype(code='BILLING')]
        self.repo.get_all.return_value = expected
        result = self.uc.execute()
        self.assertEqual(result, expected)

    def test_returns_empty_list(self):
        self.repo.get_all.return_value = []
        self.assertEqual(self.uc.execute(), [])

    def test_delegates_to_repository(self):
        self.repo.get_all.return_value = []
        self.uc.execute()
        self.repo.get_all.assert_called_once()


# ── GetParameterTypeByIdUseCase ──────────────────────────────────────────────


class TestGetParameterTypeById(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = GetParameterTypeByIdUseCase(self.repo)

    def test_returns_type_when_found(self):
        pt = _ptype()
        self.repo.get_by_id.return_value = pt
        result = self.uc.execute(pt.id)
        self.assertEqual(result, pt)

    def test_raises_not_found_when_missing(self):
        self.repo.get_by_id.return_value = None
        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute(uuid.uuid4())
        self.assertEqual(ctx.exception.code, AppErrorCode.PTYPE_NOT_FOUND)

    def test_passes_id_to_repository(self):
        tid = uuid.uuid4()
        self.repo.get_by_id.return_value = _ptype(id=tid)
        self.uc.execute(tid)
        self.repo.get_by_id.assert_called_once_with(tid)


# ── CreateParameterTypeUseCase ───────────────────────────────────────────────


class TestCreateParameterType(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = CreateParameterTypeUseCase(self.repo)

    def _data(self, **overrides):
        defaults = dict(code='NEW_TYPE', name='New Type')
        defaults.update(overrides)
        return CreateParameterTypeSchema(**defaults)

    def test_creates_type_successfully(self):
        data = self._data()
        expected = _ptype(code=data.code)
        self.repo.get_by_code.return_value = None
        self.repo.create.return_value = expected
        result = self.uc.execute(data)
        self.assertEqual(result, expected)

    def test_raises_conflict_when_code_exists(self):
        data = self._data(code='EXISTING')
        self.repo.get_by_code.return_value = _ptype(code='EXISTING')
        with self.assertRaises(ConflictException) as ctx:
            self.uc.execute(data)
        self.assertEqual(ctx.exception.code, AppErrorCode.PTYPE_DUPLICATE_CODE)

    def test_checks_code_uniqueness(self):
        data = self._data()
        self.repo.get_by_code.return_value = None
        self.repo.create.return_value = _ptype()
        self.uc.execute(data)
        self.repo.get_by_code.assert_called_once_with(data.code)

    def test_passes_schema_to_repository_create(self):
        data = self._data()
        self.repo.get_by_code.return_value = None
        self.repo.create.return_value = _ptype()
        self.uc.execute(data)
        self.repo.create.assert_called_once_with(data)


# ── UpdateParameterTypeUseCase ───────────────────────────────────────────────


class TestUpdateParameterType(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = UpdateParameterTypeUseCase(self.repo)

    def test_updates_type_successfully(self):
        tid = uuid.uuid4()
        updated = _ptype(id=tid, name='Updated')
        self.repo.get_by_code.return_value = None
        self.repo.update.return_value = updated
        data = UpdateParameterTypeSchema(name='Updated')
        result = self.uc.execute(tid, data)
        self.assertEqual(result, updated)

    def test_raises_conflict_when_new_code_taken_by_other(self):
        tid = uuid.uuid4()
        other_id = uuid.uuid4()
        self.repo.get_by_code.return_value = _ptype(id=other_id, code='TAKEN')
        data = UpdateParameterTypeSchema(code='TAKEN')
        with self.assertRaises(ConflictException) as ctx:
            self.uc.execute(tid, data)
        self.assertEqual(ctx.exception.code, AppErrorCode.PTYPE_DUPLICATE_CODE)

    def test_allows_keeping_same_code(self):
        tid = uuid.uuid4()
        self.repo.get_by_code.return_value = _ptype(id=tid, code='SAME')
        self.repo.update.return_value = _ptype(id=tid)
        data = UpdateParameterTypeSchema(code='SAME')
        self.uc.execute(tid, data)
        self.repo.update.assert_called_once_with(tid, data)

    def test_skips_code_check_when_code_not_in_update(self):
        tid = uuid.uuid4()
        self.repo.update.return_value = _ptype(id=tid)
        data = UpdateParameterTypeSchema(name='Only Name')
        self.uc.execute(tid, data)
        self.repo.get_by_code.assert_not_called()

    def test_raises_not_found_when_update_returns_none(self):
        tid = uuid.uuid4()
        self.repo.update.return_value = None
        data = UpdateParameterTypeSchema(name='Nope')
        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute(tid, data)
        self.assertEqual(ctx.exception.code, AppErrorCode.PTYPE_NOT_FOUND)


# ── DeleteParameterTypeUseCase ───────────────────────────────────────────────


class TestDeleteParameterType(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = DeleteParameterTypeUseCase(self.repo)

    def test_deletes_type(self):
        tid = uuid.uuid4()
        self.repo.delete.return_value = True
        result = self.uc.execute(tid)
        self.assertTrue(result)

    def test_raises_not_found_when_missing(self):
        self.repo.delete.return_value = False
        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute(uuid.uuid4())
        self.assertEqual(ctx.exception.code, AppErrorCode.PTYPE_NOT_FOUND)

    def test_passes_id_to_repository(self):
        tid = uuid.uuid4()
        self.repo.delete.return_value = True
        self.uc.execute(tid)
        self.repo.delete.assert_called_once_with(tid)
