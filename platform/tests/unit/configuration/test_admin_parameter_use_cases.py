"""Unit tests for admin parameter CRUD use cases."""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.errors.codes import AppErrorCode
from core.errors.exceptions import ConflictException, NotFoundException, ValidationAppException
from platform.features.configuration.admin_parameters.admin_parameter.application.use_cases import (
    CreateAdminParameterUseCase,
    DeleteAdminParameterUseCase,
    GetAdminParameterByIdUseCase,
    UpdateAdminParameterUseCase,
)
from platform.features.configuration.admin_parameters.admin_parameter.domain.schemas import (
    AdminParameterSchema,
    CreateAdminParameterSchema,
    UpdateAdminParameterSchema,
)
from platform.features.configuration.admin_parameters.admin_parameter_type.application.use_cases import (
    DeleteAdminParameterTypeUseCase,
)
from platform.features.configuration.admin_parameters.admin_parameter_type.domain.schemas import (
    AdminParameterTypeSchema,
)

PTYPE_ID = uuid.uuid4()


def _param(**overrides) -> AdminParameterSchema:
    defaults = dict(
        id=uuid.uuid4(),
        parameter_type=PTYPE_ID,
        code='TOKEN_DURATION',
        name='Token Duration',
        description='Access TTL',
        data_type='INT',
        value='30',
        is_active=True,
    )
    defaults.update(overrides)
    return AdminParameterSchema(**defaults)


def _ptype(**overrides) -> AdminParameterTypeSchema:
    defaults = dict(
        id=PTYPE_ID,
        code='SECURITY',
        name='Security',
        description='',
        is_active=True,
    )
    defaults.update(overrides)
    return AdminParameterTypeSchema(**defaults)


class TestCreateAdminParameterUseCase(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.type_repo = MagicMock()
        self.type_repo.get_by_id.return_value = _ptype()
        self.uc = CreateAdminParameterUseCase(self.repo, self.type_repo)

    @patch('platform.features.configuration.admin_parameters.admin_parameter.application.use_cases.clear_admin_parameter_cache')
    @patch('platform.features.configuration.admin_parameters.admin_parameter.application.use_cases.invalidate_cache')
    def test_create_success(self, _inv, _clear):
        self.repo.get_by_code.return_value = None
        created = _param()
        self.repo.create.return_value = created
        data = CreateAdminParameterSchema(
            parameter_type=PTYPE_ID,
            code='TOKEN_DURATION',
            name='Token Duration',
            data_type='INT',
            value='30',
        )
        result = self.uc.execute(data)
        self.assertEqual(result.code, 'TOKEN_DURATION')
        self.repo.create.assert_called_once()

    def test_type_not_found(self):
        self.type_repo.get_by_id.return_value = None
        data = CreateAdminParameterSchema(
            parameter_type=PTYPE_ID,
            code='TOKEN_DURATION',
            name='Token Duration',
            data_type='INT',
            value='30',
        )
        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute(data)
        self.assertEqual(ctx.exception.code, AppErrorCode.APTYPE_NOT_FOUND)

    def test_duplicate_code(self):
        self.repo.get_by_code.return_value = _param()
        data = CreateAdminParameterSchema(
            parameter_type=PTYPE_ID,
            code='TOKEN_DURATION',
            name='Token Duration',
            data_type='INT',
            value='30',
        )
        with self.assertRaises(ConflictException) as ctx:
            self.uc.execute(data)
        self.assertEqual(ctx.exception.code, AppErrorCode.APARAM_DUPLICATE_CODE)

    def test_invalid_data_type(self):
        data = CreateAdminParameterSchema(
            parameter_type=PTYPE_ID,
            code='BAD_TYPE',
            name='Bad Type',
            data_type='XML',
            value='x',
        )
        with self.assertRaises(ValidationAppException) as ctx:
            self.uc.execute(data)
        self.assertEqual(ctx.exception.code, AppErrorCode.APARAM_INVALID_DATA_TYPE)

    def test_invalid_value_uses_aparam_code(self):
        data = CreateAdminParameterSchema(
            parameter_type=PTYPE_ID,
            code='BAD_VALUE',
            name='Bad Value',
            data_type='INT',
            value='not-a-number',
        )
        with self.assertRaises(ValidationAppException) as ctx:
            self.uc.execute(data)
        self.assertEqual(ctx.exception.code, AppErrorCode.APARAM_INVALID_VALUE)


class TestGetDeleteUpdateAdminParameter(TestCase):

    def test_get_not_found(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        with self.assertRaises(NotFoundException) as ctx:
            GetAdminParameterByIdUseCase(repo).execute(uuid.uuid4())
        self.assertEqual(ctx.exception.code, AppErrorCode.APARAM_NOT_FOUND)

    @patch('platform.features.configuration.admin_parameters.admin_parameter.application.use_cases.clear_admin_parameter_cache')
    @patch('platform.features.configuration.admin_parameters.admin_parameter.application.use_cases.invalidate_cache')
    def test_delete_success(self, _inv, _clear):
        repo = MagicMock()
        existing = _param()
        repo.get_by_id.return_value = existing
        repo.delete.return_value = True
        self.assertTrue(DeleteAdminParameterUseCase(repo).execute(existing.id))
        _clear.assert_called_with(existing.code)

    @patch('platform.features.configuration.admin_parameters.admin_parameter.application.use_cases.clear_admin_parameter_cache')
    @patch('platform.features.configuration.admin_parameters.admin_parameter.application.use_cases.clear_inactivity_cache')
    @patch('platform.features.configuration.admin_parameters.admin_parameter.application.use_cases.invalidate_cache')
    def test_update_clears_inactivity_cache_for_idle_param(self, _inv, clear_idle, clear_param):
        repo = MagicMock()
        type_repo = MagicMock()
        existing = _param(code='TIME_INACTIVITY', value='15')
        repo.get_by_id.return_value = existing
        repo.get_by_code.return_value = None
        repo.update.return_value = _param(code='TIME_INACTIVITY', value='30')
        UpdateAdminParameterUseCase(repo, type_repo).execute(
            existing.id,
            UpdateAdminParameterSchema(value='30'),
        )
        clear_idle.assert_called_once()
        clear_param.assert_called_with('TIME_INACTIVITY')


class TestDeleteAdminParameterTypeUseCase(TestCase):

    def test_rejects_when_parameters_exist(self):
        type_repo = MagicMock()
        param_repo = MagicMock()
        type_repo.get_by_id.return_value = _ptype()
        param_repo.count_by_type.return_value = 2
        with self.assertRaises(ConflictException) as ctx:
            DeleteAdminParameterTypeUseCase(type_repo, param_repo).execute(PTYPE_ID)
        self.assertEqual(ctx.exception.code, AppErrorCode.APTYPE_IN_USE)
        type_repo.delete.assert_not_called()

    @patch(
        'platform.features.configuration.admin_parameters.admin_parameter_type'
        '.application.use_cases.invalidate_cache',
    )
    def test_delete_when_empty(self, _inv):
        type_repo = MagicMock()
        param_repo = MagicMock()
        type_repo.get_by_id.return_value = _ptype()
        param_repo.count_by_type.return_value = 0
        type_repo.delete.return_value = True
        self.assertTrue(
            DeleteAdminParameterTypeUseCase(type_repo, param_repo).execute(PTYPE_ID),
        )
