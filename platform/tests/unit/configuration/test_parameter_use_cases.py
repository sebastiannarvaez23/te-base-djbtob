"""
Unit tests for Parameter CRUD use cases.

Covers:
- Success paths for all data types (STRING, INT, DECIMAL, BOOL, JSON)
- Failure paths: duplicate code, not found, invalid data type, invalid value per type
- Cache integration: HIT/MISS on reads, invalidation on writes
"""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.cache import TTL
from core.errors.exceptions import ConflictException, NotFoundException, ValidationAppException
from core.errors.codes import AppErrorCode
from core.validators import DataTypeValueValidator
from platform.features.configuration.parameters.parameter.application.use_cases import (
    GetAllParametersUseCase,
    GetParameterByIdUseCase,
    CreateParameterUseCase,
    UpdateParameterUseCase,
    DeleteParameterUseCase,
)
from platform.features.configuration.parameters.parameter.domain.schemas import (
    CreateParameterSchema,
    ParameterSchema,
    UpdateParameterSchema,
)

PTYPE_ID = uuid.uuid4()


def _param(**overrides) -> ParameterSchema:
    defaults = dict(
        id=uuid.uuid4(),
        parameter_type=PTYPE_ID,
        code='MAX_RETRIES',
        name='Max Retries',
        description='Maximum login retries',
        data_type='INT',
        value='3',
        is_active=True,
    )
    defaults.update(overrides)
    return ParameterSchema(**defaults)


def _create_data(**overrides) -> CreateParameterSchema:
    defaults = dict(
        parameter_type=PTYPE_ID,
        code='NEW_PARAM',
        name='New Param',
        data_type='STRING',
        value='hello',
    )
    defaults.update(overrides)
    return CreateParameterSchema(**defaults)


# ── DataTypeValueValidator.validate ─────────────────────────────────────────────


class TestValidateValueForDataType(TestCase):

    # ── STRING ────────────────────────────────────────────────────────────
    def test_string_accepts_any_text(self):
        DataTypeValueValidator.validate('anything', 'STRING')  # no exception

    def test_string_accepts_empty(self):
        DataTypeValueValidator.validate('', 'STRING')

    # ── INT ───────────────────────────────────────────────────────────────
    def test_int_accepts_positive(self):
        DataTypeValueValidator.validate('42', 'INT')

    def test_int_accepts_negative(self):
        DataTypeValueValidator.validate('-7', 'INT')

    def test_int_accepts_zero(self):
        DataTypeValueValidator.validate('0', 'INT')

    def test_int_rejects_float_string(self):
        with self.assertRaises(ValidationAppException) as ctx:
            DataTypeValueValidator.validate('3.14', 'INT')
        self.assertEqual(ctx.exception.code, AppErrorCode.PARAM_INVALID_VALUE)

    def test_int_rejects_text(self):
        with self.assertRaises(ValidationAppException):
            DataTypeValueValidator.validate('abc', 'INT')

    def test_int_rejects_empty(self):
        with self.assertRaises(ValidationAppException):
            DataTypeValueValidator.validate('', 'INT')

    # ── DECIMAL ───────────────────────────────────────────────────────────
    def test_decimal_accepts_float(self):
        DataTypeValueValidator.validate('19.5', 'DECIMAL')

    def test_decimal_accepts_integer_string(self):
        DataTypeValueValidator.validate('100', 'DECIMAL')

    def test_decimal_accepts_negative(self):
        DataTypeValueValidator.validate('-0.5', 'DECIMAL')

    def test_decimal_rejects_text(self):
        with self.assertRaises(ValidationAppException) as ctx:
            DataTypeValueValidator.validate('not-a-number', 'DECIMAL')
        self.assertEqual(ctx.exception.code, AppErrorCode.PARAM_INVALID_VALUE)

    def test_decimal_rejects_empty(self):
        with self.assertRaises(ValidationAppException):
            DataTypeValueValidator.validate('', 'DECIMAL')

    # ── BOOL ──────────────────────────────────────────────────────────────
    def test_bool_accepts_true(self):
        DataTypeValueValidator.validate('true', 'BOOL')

    def test_bool_accepts_false(self):
        DataTypeValueValidator.validate('false', 'BOOL')

    def test_bool_accepts_1(self):
        DataTypeValueValidator.validate('1', 'BOOL')

    def test_bool_accepts_0(self):
        DataTypeValueValidator.validate('0', 'BOOL')

    def test_bool_accepts_yes(self):
        DataTypeValueValidator.validate('yes', 'BOOL')

    def test_bool_accepts_no(self):
        DataTypeValueValidator.validate('no', 'BOOL')

    def test_bool_accepts_case_insensitive(self):
        DataTypeValueValidator.validate('TRUE', 'BOOL')
        DataTypeValueValidator.validate('False', 'BOOL')
        DataTypeValueValidator.validate('YES', 'BOOL')

    def test_bool_rejects_arbitrary_text(self):
        with self.assertRaises(ValidationAppException) as ctx:
            DataTypeValueValidator.validate('maybe', 'BOOL')
        self.assertEqual(ctx.exception.code, AppErrorCode.PARAM_INVALID_VALUE)

    def test_bool_rejects_empty(self):
        with self.assertRaises(ValidationAppException):
            DataTypeValueValidator.validate('', 'BOOL')

    # ── JSON ──────────────────────────────────────────────────────────────
    def test_json_accepts_object(self):
        DataTypeValueValidator.validate('{"key": "value"}', 'JSON')

    def test_json_accepts_array(self):
        DataTypeValueValidator.validate('[1, 2, 3]', 'JSON')

    def test_json_accepts_string(self):
        DataTypeValueValidator.validate('"hello"', 'JSON')

    def test_json_accepts_number(self):
        DataTypeValueValidator.validate('42', 'JSON')

    def test_json_accepts_null(self):
        DataTypeValueValidator.validate('null', 'JSON')

    def test_json_rejects_invalid(self):
        with self.assertRaises(ValidationAppException) as ctx:
            DataTypeValueValidator.validate('{invalid}', 'JSON')
        self.assertEqual(ctx.exception.code, AppErrorCode.PARAM_INVALID_VALUE)

    def test_json_rejects_empty(self):
        with self.assertRaises(ValidationAppException):
            DataTypeValueValidator.validate('', 'JSON')


# ── GetAllParametersUseCase ──────────────────────────────────────────────────


class TestGetAllParameters(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = GetAllParametersUseCase(self.repo)
        patcher = patch('core.cache.decorators.caches')
        self.mock_caches = patcher.start()
        self.mock_cache = MagicMock()
        self.mock_caches.__getitem__ = MagicMock(return_value=self.mock_cache)
        self.mock_cache.get.return_value = None
        self.addCleanup(patcher.stop)

    def test_returns_all_parameters(self):
        expected = [_param(), _param(code='CURRENCY')]
        self.repo.get_all.return_value = expected
        self.assertEqual(self.uc.execute(), expected)

    def test_returns_empty_list(self):
        self.repo.get_all.return_value = []
        self.assertEqual(self.uc.execute(), [])


# ── GetParameterByIdUseCase ──────────────────────────────────────────────────


class TestGetParameterById(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = GetParameterByIdUseCase(self.repo)
        patcher = patch('core.cache.decorators.caches')
        self.mock_caches = patcher.start()
        self.mock_cache = MagicMock()
        self.mock_caches.__getitem__ = MagicMock(return_value=self.mock_cache)
        self.mock_cache.get.return_value = None
        self.addCleanup(patcher.stop)

    def test_returns_parameter_when_found(self):
        p = _param()
        self.repo.get_by_id.return_value = p
        self.assertEqual(self.uc.execute(p.id), p)

    def test_raises_not_found_when_missing(self):
        self.repo.get_by_id.return_value = None
        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute(uuid.uuid4())
        self.assertEqual(ctx.exception.code, AppErrorCode.PARAM_NOT_FOUND)


# ── CreateParameterUseCase ───────────────────────────────────────────────────


class TestCreateParameter(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = CreateParameterUseCase(self.repo)

    def test_creates_string_parameter(self):
        data = _create_data(data_type='STRING', value='hello')
        expected = _param(code=data.code, data_type='STRING', value='hello')
        self.repo.get_by_code.return_value = None
        self.repo.create.return_value = expected
        result = self.uc.execute(data)
        self.assertEqual(result, expected)

    def test_creates_int_parameter(self):
        data = _create_data(data_type='INT', value='42')
        expected = _param(code=data.code, data_type='INT', value='42')
        self.repo.get_by_code.return_value = None
        self.repo.create.return_value = expected
        result = self.uc.execute(data)
        self.assertEqual(result, expected)

    def test_creates_decimal_parameter(self):
        data = _create_data(data_type='DECIMAL', value='19.5')
        expected = _param(code=data.code, data_type='DECIMAL', value='19.5')
        self.repo.get_by_code.return_value = None
        self.repo.create.return_value = expected
        result = self.uc.execute(data)
        self.assertEqual(result, expected)

    def test_creates_bool_parameter(self):
        data = _create_data(data_type='BOOL', value='true')
        expected = _param(code=data.code, data_type='BOOL', value='true')
        self.repo.get_by_code.return_value = None
        self.repo.create.return_value = expected
        result = self.uc.execute(data)
        self.assertEqual(result, expected)

    def test_creates_json_parameter(self):
        data = _create_data(data_type='JSON', value='{"smtp": "localhost"}')
        expected = _param(code=data.code, data_type='JSON', value='{"smtp": "localhost"}')
        self.repo.get_by_code.return_value = None
        self.repo.create.return_value = expected
        result = self.uc.execute(data)
        self.assertEqual(result, expected)

    def test_raises_conflict_when_code_exists(self):
        data = _create_data(code='EXISTING')
        self.repo.get_by_code.return_value = _param(code='EXISTING')
        with self.assertRaises(ConflictException) as ctx:
            self.uc.execute(data)
        self.assertEqual(ctx.exception.code, AppErrorCode.PARAM_DUPLICATE_CODE)

    def test_raises_validation_for_invalid_data_type(self):
        data = _create_data(data_type='INVALID_TYPE', value='x')
        with self.assertRaises(ValidationAppException) as ctx:
            self.uc.execute(data)
        self.assertEqual(ctx.exception.code, AppErrorCode.PARAM_INVALID_DATA_TYPE)

    def test_raises_validation_for_int_with_non_numeric_value(self):
        data = _create_data(data_type='INT', value='not_a_number')
        with self.assertRaises(ValidationAppException) as ctx:
            self.uc.execute(data)
        self.assertEqual(ctx.exception.code, AppErrorCode.PARAM_INVALID_VALUE)

    def test_raises_validation_for_decimal_with_non_numeric_value(self):
        data = _create_data(data_type='DECIMAL', value='abc')
        with self.assertRaises(ValidationAppException) as ctx:
            self.uc.execute(data)
        self.assertEqual(ctx.exception.code, AppErrorCode.PARAM_INVALID_VALUE)

    def test_raises_validation_for_bool_with_invalid_value(self):
        data = _create_data(data_type='BOOL', value='maybe')
        with self.assertRaises(ValidationAppException) as ctx:
            self.uc.execute(data)
        self.assertEqual(ctx.exception.code, AppErrorCode.PARAM_INVALID_VALUE)

    def test_raises_validation_for_json_with_invalid_value(self):
        data = _create_data(data_type='JSON', value='{bad json}')
        with self.assertRaises(ValidationAppException) as ctx:
            self.uc.execute(data)
        self.assertEqual(ctx.exception.code, AppErrorCode.PARAM_INVALID_VALUE)

    def test_does_not_check_code_when_validation_fails(self):
        data = _create_data(data_type='INVALID_TYPE', value='x')
        with self.assertRaises(ValidationAppException):
            self.uc.execute(data)
        self.repo.get_by_code.assert_not_called()


# ── UpdateParameterUseCase ───────────────────────────────────────────────────


class TestUpdateParameter(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = UpdateParameterUseCase(self.repo)

    def test_updates_value_successfully(self):
        pid = uuid.uuid4()
        existing = _param(id=pid, data_type='INT', value='3')
        updated = _param(id=pid, data_type='INT', value='5')
        self.repo.get_by_id.return_value = existing
        self.repo.update.return_value = updated
        data = UpdateParameterSchema(value='5')
        result = self.uc.execute(pid, data)
        self.assertEqual(result, updated)

    def test_validates_new_value_against_existing_data_type(self):
        pid = uuid.uuid4()
        existing = _param(id=pid, data_type='INT', value='3')
        self.repo.get_by_id.return_value = existing
        data = UpdateParameterSchema(value='not_int')
        with self.assertRaises(ValidationAppException) as ctx:
            self.uc.execute(pid, data)
        self.assertEqual(ctx.exception.code, AppErrorCode.PARAM_INVALID_VALUE)

    def test_validates_existing_value_against_new_data_type(self):
        pid = uuid.uuid4()
        existing = _param(id=pid, data_type='STRING', value='hello')
        self.repo.get_by_id.return_value = existing
        data = UpdateParameterSchema(data_type='INT')
        with self.assertRaises(ValidationAppException) as ctx:
            self.uc.execute(pid, data)
        self.assertEqual(ctx.exception.code, AppErrorCode.PARAM_INVALID_VALUE)

    def test_validates_both_new_value_and_new_data_type(self):
        pid = uuid.uuid4()
        existing = _param(id=pid, data_type='STRING', value='old')
        self.repo.get_by_id.return_value = existing
        self.repo.update.return_value = _param(id=pid, data_type='DECIMAL', value='9.99')
        data = UpdateParameterSchema(data_type='DECIMAL', value='9.99')
        result = self.uc.execute(pid, data)
        self.assertEqual(result.value, '9.99')

    def test_raises_conflict_when_new_code_taken_by_other(self):
        pid = uuid.uuid4()
        other_id = uuid.uuid4()
        existing = _param(id=pid)
        self.repo.get_by_id.return_value = existing
        self.repo.get_by_code.return_value = _param(id=other_id, code='TAKEN')
        data = UpdateParameterSchema(code='TAKEN')
        with self.assertRaises(ConflictException) as ctx:
            self.uc.execute(pid, data)
        self.assertEqual(ctx.exception.code, AppErrorCode.PARAM_DUPLICATE_CODE)

    def test_allows_keeping_same_code(self):
        pid = uuid.uuid4()
        existing = _param(id=pid, code='SAME')
        self.repo.get_by_id.return_value = existing
        self.repo.get_by_code.return_value = _param(id=pid, code='SAME')
        self.repo.update.return_value = _param(id=pid)
        data = UpdateParameterSchema(code='SAME')
        self.uc.execute(pid, data)
        self.repo.update.assert_called_once_with(pid, data)

    def test_skips_validation_when_no_value_or_type_change(self):
        pid = uuid.uuid4()
        existing = _param(id=pid)
        self.repo.get_by_id.return_value = existing
        self.repo.update.return_value = _param(id=pid, name='Renamed')
        data = UpdateParameterSchema(name='Renamed')
        result = self.uc.execute(pid, data)
        self.assertEqual(result.name, 'Renamed')

    def test_raises_not_found_when_parameter_missing(self):
        self.repo.get_by_id.return_value = None
        data = UpdateParameterSchema(name='Nope')
        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute(uuid.uuid4(), data)
        self.assertEqual(ctx.exception.code, AppErrorCode.PARAM_NOT_FOUND)

    def test_raises_not_found_when_update_returns_none(self):
        pid = uuid.uuid4()
        existing = _param(id=pid)
        self.repo.get_by_id.return_value = existing
        self.repo.update.return_value = None
        data = UpdateParameterSchema(name='Nope')
        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute(pid, data)
        self.assertEqual(ctx.exception.code, AppErrorCode.PARAM_NOT_FOUND)

    def test_rejects_invalid_data_type_on_update(self):
        pid = uuid.uuid4()
        existing = _param(id=pid)
        self.repo.get_by_id.return_value = existing
        data = UpdateParameterSchema(data_type='UNKNOWN')
        with self.assertRaises(ValidationAppException) as ctx:
            self.uc.execute(pid, data)
        self.assertEqual(ctx.exception.code, AppErrorCode.PARAM_INVALID_DATA_TYPE)


# ── DeleteParameterUseCase ───────────────────────────────────────────────────


class TestDeleteParameter(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = DeleteParameterUseCase(self.repo)

    def test_deletes_parameter(self):
        pid = uuid.uuid4()
        existing = _param(id=pid, code='TO_DELETE')
        self.repo.get_by_id.return_value = existing
        self.repo.delete.return_value = True
        result = self.uc.execute(pid)
        self.assertTrue(result)

    def test_raises_not_found_when_missing(self):
        self.repo.get_by_id.return_value = None
        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute(uuid.uuid4())
        self.assertEqual(ctx.exception.code, AppErrorCode.PARAM_NOT_FOUND)

    def test_passes_id_to_repository(self):
        pid = uuid.uuid4()
        self.repo.get_by_id.return_value = _param(id=pid, code='X')
        self.repo.delete.return_value = True
        self.uc.execute(pid)
        self.repo.delete.assert_called_once_with(pid)


# ── Cache integration ───────────────────────────────────────────────────────


class TestGetAllParametersCache(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = GetAllParametersUseCase(self.repo)

    @patch('core.cache.decorators.caches')
    def test_returns_cached_list_without_hitting_repo(self, mock_caches):
        mock_cache = MagicMock()
        mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
        cached = [_param(), _param(code='CURRENCY')]
        mock_cache.get.return_value = cached

        result = self.uc.execute()

        self.assertEqual(result, cached)
        self.repo.get_all.assert_not_called()

    @patch('core.cache.decorators.caches')
    def test_queries_repo_and_caches_on_miss(self, mock_caches):
        mock_cache = MagicMock()
        mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
        mock_cache.get.return_value = None
        expected = [_param()]
        self.repo.get_all.return_value = expected

        result = self.uc.execute()

        self.assertEqual(result, expected)
        self.repo.get_all.assert_called_once()
        mock_cache.set.assert_called_once_with('parameters', expected, timeout=TTL)


class TestGetParameterByIdCache(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = GetParameterByIdUseCase(self.repo)

    @patch('core.cache.decorators.caches')
    def test_returns_cached_parameter_without_hitting_repo(self, mock_caches):
        mock_cache = MagicMock()
        mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
        pid = uuid.uuid4()
        cached = _param(id=pid)
        mock_cache.get.return_value = cached

        result = self.uc.execute(pid)

        self.assertEqual(result, cached)
        self.repo.get_by_id.assert_not_called()

    @patch('core.cache.decorators.caches')
    def test_uses_parameter_id_as_cache_key(self, mock_caches):
        mock_cache = MagicMock()
        mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
        mock_cache.get.return_value = None
        pid = uuid.uuid4()
        expected = _param(id=pid)
        self.repo.get_by_id.return_value = expected

        self.uc.execute(pid)

        mock_cache.get.assert_called_once_with(f'parameters:{pid}')
        mock_cache.set.assert_called_once_with(f'parameters:{pid}', expected, timeout=TTL)


class TestCreateParameterCacheInvalidation(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = CreateParameterUseCase(self.repo)

    @patch('core.cache.invalidation.caches')
    def test_invalidates_cache_after_create(self, mock_caches):
        mock_cache = MagicMock()
        mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
        data = _create_data()
        self.repo.get_by_code.return_value = None
        self.repo.create.return_value = _param(code=data.code)

        self.uc.execute(data)

        mock_cache.delete_pattern.assert_called_once_with('parameters:*')

    @patch('core.cache.invalidation.caches')
    def test_does_not_invalidate_on_conflict(self, mock_caches):
        mock_cache = MagicMock()
        mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
        data = _create_data(code='EXISTING')
        self.repo.get_by_code.return_value = _param(code='EXISTING')

        with self.assertRaises(ConflictException):
            self.uc.execute(data)

        mock_cache.delete_pattern.assert_not_called()


class TestUpdateParameterCacheInvalidation(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = UpdateParameterUseCase(self.repo)

    @patch('core.cache.invalidation.caches')
    def test_invalidates_cache_after_update(self, mock_caches):
        mock_cache = MagicMock()
        mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
        pid = uuid.uuid4()
        existing = _param(id=pid, data_type='INT', value='3')
        self.repo.get_by_id.return_value = existing
        self.repo.update.return_value = _param(id=pid, data_type='INT', value='5')

        self.uc.execute(pid, UpdateParameterSchema(value='5'))

        mock_cache.delete_pattern.assert_called_once_with('parameters:*')

    @patch('core.cache.invalidation.caches')
    def test_does_not_invalidate_on_not_found(self, mock_caches):
        mock_cache = MagicMock()
        mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
        self.repo.get_by_id.return_value = None

        with self.assertRaises(NotFoundException):
            self.uc.execute(uuid.uuid4(), UpdateParameterSchema(name='Nope'))

        mock_cache.delete_pattern.assert_not_called()


class TestDeleteParameterCacheInvalidation(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = DeleteParameterUseCase(self.repo)

    @patch('core.cache.invalidation.caches')
    def test_invalidates_cache_after_delete(self, mock_caches):
        mock_cache = MagicMock()
        mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
        pid = uuid.uuid4()
        self.repo.get_by_id.return_value = _param(id=pid, code='GONE')
        self.repo.delete.return_value = True

        self.uc.execute(pid)

        mock_cache.delete_pattern.assert_called_once_with('parameters:*')

    @patch('core.cache.invalidation.caches')
    def test_does_not_invalidate_on_not_found(self, mock_caches):
        mock_cache = MagicMock()
        mock_caches.__getitem__ = MagicMock(return_value=mock_cache)
        self.repo.get_by_id.return_value = None

        with self.assertRaises(NotFoundException):
            self.uc.execute(uuid.uuid4())

        mock_cache.delete_pattern.assert_not_called()
