"""
Unit tests for platform admin roles and permissions use cases.

Mirrors client role tests, without multi-tenant restrictions:
  - ListAdminRolesUseCase
  - CreateAdminRoleUseCase
  - UpdateAdminRoleUseCase
  - DeleteAdminRoleUseCase
  - ListAdminModulesUseCase
  - ListAdminFeaturesUseCase
  - UpdateAdminRoleFeaturesUseCase

No database required — repositories are mocked.
"""
import uuid
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock

from platform.features.security.access.roles.application.use_cases import (
    CreateAdminRoleUseCase,
    DeleteAdminRoleUseCase,
    ListAdminFeaturesUseCase,
    ListAdminModulesUseCase,
    ListAdminRolesUseCase,
    UpdateAdminRoleFeaturesUseCase,
    UpdateAdminRoleUseCase,
)
from platform.features.security.access.roles.domain.schemas import (
    AdminModuleSchema,
    AdminRoleSchema,
    CreateAdminRoleSchema,
    FeatureCatalogItemSchema,
    UpdateAdminRoleFeaturesSchema,
    UpdateAdminRoleSchema,
)

_NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)
ROLE_ID = uuid.uuid4()


def _feature(**overrides) -> FeatureCatalogItemSchema:
    defaults = dict(
        key='admin.tenants.view',
        module='tenants',
        label='Ver empresas',
        category='features',
    )
    defaults.update(overrides)
    return FeatureCatalogItemSchema(**defaults)


def _role(**overrides) -> AdminRoleSchema:
    defaults = dict(
        id=uuid.uuid4(),
        name='Operator',
        description='Rol de operador de plataforma',
        is_active=True,
        is_generic=False,
        is_editable=True,
        features=[],
        modules=[],
        created_at=_NOW,
        updated_at=_NOW,
    )
    defaults.update(overrides)
    return AdminRoleSchema(**defaults)


# ── ListAdminRolesUseCase ──────────────────────────────────────────────────────

class TestListAdminRolesUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = ListAdminRolesUseCase(self.mock_repo)

    def test_returns_list_of_roles(self):
        roles = [_role(name='Admin'), _role(name='Operator')]
        self.mock_repo.get_all.return_value = roles

        result = self.use_case.execute()

        self.assertEqual(len(result), 2)
        self.mock_repo.get_all.assert_called_once_with(filters=None)

    def test_returns_empty_list_when_no_roles_exist(self):
        self.mock_repo.get_all.return_value = []

        result = self.use_case.execute()

        self.assertEqual(result, [])

    def test_roles_include_feature_keys(self):
        role_with_features = _role(features=['admin.tenants.view', 'admin.users.view'])
        self.mock_repo.get_all.return_value = [role_with_features]

        result = self.use_case.execute()

        self.assertIn('admin.tenants.view', result[0].features)
        self.assertIn('admin.users.view', result[0].features)

    def test_roles_include_module_codes(self):
        role_with_modules = _role(modules=['tenants', 'users'])
        self.mock_repo.get_all.return_value = [role_with_modules]

        result = self.use_case.execute()

        self.assertEqual(result[0].modules, ['tenants', 'users'])

    def test_all_roles_are_editable(self):
        """Admin roles have no universal/generic protection — all are editable."""
        self.mock_repo.get_all.return_value = [_role(is_editable=True)]

        result = self.use_case.execute()

        self.assertTrue(result[0].is_editable)
        self.assertFalse(result[0].is_generic)


# ── CreateAdminRoleUseCase ─────────────────────────────────────────────────────

class TestCreateAdminRoleUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = CreateAdminRoleUseCase(self.mock_repo)

    def test_delegates_creation_to_repository(self):
        data = CreateAdminRoleSchema(name='Supervisor', is_active=True)
        created = _role(name='Supervisor')
        self.mock_repo.create.return_value = created

        result = self.use_case.execute(data)

        self.mock_repo.create.assert_called_once_with(data)
        self.assertEqual(result.name, 'Supervisor')

    def test_created_role_starts_without_features(self):
        data = CreateAdminRoleSchema(name='New Role')
        self.mock_repo.create.return_value = _role(name='New Role', features=[], modules=[])

        result = self.use_case.execute(data)

        self.assertEqual(result.features, [])
        self.assertEqual(result.modules, [])

    def test_created_role_is_active_by_default(self):
        data = CreateAdminRoleSchema(name='New Role', is_active=True)
        self.mock_repo.create.return_value = _role(is_active=True)

        result = self.use_case.execute(data)

        self.assertTrue(result.is_active)


# ── UpdateAdminRoleUseCase ─────────────────────────────────────────────────────

class TestUpdateAdminRoleUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = UpdateAdminRoleUseCase(self.mock_repo)

    def test_delegates_update_to_repository(self):
        data = UpdateAdminRoleSchema(name='Senior Supervisor')
        updated = _role(id=ROLE_ID, name='Senior Supervisor')
        self.mock_repo.update.return_value = updated

        result = self.use_case.execute(ROLE_ID, data)

        self.mock_repo.update.assert_called_once_with(ROLE_ID, data)
        self.assertEqual(result.name, 'Senior Supervisor')

    def test_can_deactivate_any_role(self):
        """No company-scoped protection — any admin role can be toggled."""
        data = UpdateAdminRoleSchema(is_active=False)
        self.mock_repo.update.return_value = _role(id=ROLE_ID, is_active=False)

        result = self.use_case.execute(ROLE_ID, data)

        self.assertFalse(result.is_active)

    def test_returns_none_when_role_does_not_exist(self):
        self.mock_repo.update.return_value = None

        result = self.use_case.execute(uuid.uuid4(), UpdateAdminRoleSchema())

        self.assertIsNone(result)


# ── DeleteAdminRoleUseCase ─────────────────────────────────────────────────────

class TestDeleteAdminRoleUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = DeleteAdminRoleUseCase(self.mock_repo)

    def test_returns_true_when_deletion_is_successful(self):
        self.mock_repo.delete.return_value = True

        result = self.use_case.execute(ROLE_ID)

        self.assertTrue(result)
        self.mock_repo.delete.assert_called_once_with(ROLE_ID)

    def test_returns_false_when_role_does_not_exist(self):
        self.mock_repo.delete.return_value = False

        result = self.use_case.execute(uuid.uuid4())

        self.assertFalse(result)


# ── ListAdminModulesUseCase ────────────────────────────────────────────────────

class TestListAdminModulesUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = ListAdminModulesUseCase(self.mock_repo)

    def test_returns_admin_modules_catalog(self):
        modules = [
            AdminModuleSchema(
                id=uuid.uuid4(),
                code='tenants',
                name='sidebar.tenants',
                description='',
                icon='bx-buildings',
                route='/admin/tenants',
                section_id=uuid.uuid4(),
                section_code='platform',
                section_name='Plataforma',
                section_order=1,
                order=1,
                is_active=True,
                created_at=_NOW,
                updated_at=_NOW,
            ),
        ]
        self.mock_repo.get_all_modules.return_value = modules

        result = self.use_case.execute()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].code, 'tenants')
        self.mock_repo.get_all_modules.assert_called_once_with(filters=None)

    def test_returns_empty_catalog(self):
        self.mock_repo.get_all_modules.return_value = []

        result = self.use_case.execute()

        self.assertEqual(result, [])


# ── ListAdminFeaturesUseCase ───────────────────────────────────────────────────

class TestListAdminFeaturesUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = ListAdminFeaturesUseCase(self.mock_repo)

    def test_returns_feature_catalog(self):
        catalog = [
            _feature(key='admin.tenants.view', module='tenants'),
            _feature(key='admin.users.view', module='users'),
        ]
        self.mock_repo.get_all_features.return_value = catalog

        result = self.use_case.execute()

        self.assertEqual(len(result), 2)
        self.mock_repo.get_all_features.assert_called_once_with(filters=None)

    def test_returns_empty_catalog(self):
        self.mock_repo.get_all_features.return_value = []

        result = self.use_case.execute()

        self.assertEqual(result, [])

    def test_returns_features_across_multiple_modules(self):
        features = [
            _feature(key='admin.tenants.view', module='tenants'),
            _feature(key='admin.billing.view', module='billing'),
            _feature(key='admin.users.list', module='users'),
        ]
        self.mock_repo.get_all_features.return_value = features

        result = self.use_case.execute()

        modules = {f.module for f in result}
        self.assertEqual(modules, {'tenants', 'billing', 'users'})


# ── UpdateAdminRoleFeaturesUseCase ─────────────────────────────────────────────

class TestUpdateAdminRoleFeaturesUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = UpdateAdminRoleFeaturesUseCase(self.mock_repo)

    def test_assigns_feature_keys_to_role(self):
        keys = ['admin.tenants.view', 'admin.users.view']
        data = UpdateAdminRoleFeaturesSchema(feature_keys=keys, module_codes=['tenants', 'users'])
        updated = _role(id=ROLE_ID, features=keys, modules=['tenants', 'users'])
        self.mock_repo.update_features.return_value = updated

        result = self.use_case.execute(ROLE_ID, data)

        self.mock_repo.update_features.assert_called_once_with(ROLE_ID, data)
        self.assertEqual(result.features, keys)
        self.assertEqual(result.modules, ['tenants', 'users'])

    def test_clears_all_features_when_empty_list_provided(self):
        data = UpdateAdminRoleFeaturesSchema(feature_keys=[], module_codes=[])
        self.mock_repo.update_features.return_value = _role(features=[], modules=[])

        result = self.use_case.execute(ROLE_ID, data)

        self.assertEqual(result.features, [])
        self.assertEqual(result.modules, [])

    def test_replaces_previous_features_completely(self):
        """Update is a full replace, not a partial add."""
        new_keys = ['admin.billing.view', 'admin.users.list']
        data = UpdateAdminRoleFeaturesSchema(feature_keys=new_keys, module_codes=['billing'])
        self.mock_repo.update_features.return_value = _role(
            features=new_keys, modules=['billing'],
        )

        result = self.use_case.execute(ROLE_ID, data)

        self.assertNotIn('admin.tenants.view', result.features)
        self.assertIn('admin.billing.view', result.features)
        self.assertEqual(result.modules, ['billing'])

    def test_returns_none_when_role_does_not_exist(self):
        data = UpdateAdminRoleFeaturesSchema(feature_keys=['any.feature'])
        self.mock_repo.update_features.return_value = None

        result = self.use_case.execute(uuid.uuid4(), data)

        self.assertIsNone(result)

    def test_can_assign_modules_without_features(self):
        """RolModule grants sidebar access without feature keys."""
        data = UpdateAdminRoleFeaturesSchema(feature_keys=[], module_codes=['dashboard'])
        self.mock_repo.update_features.return_value = _role(features=[], modules=['dashboard'])

        result = self.use_case.execute(ROLE_ID, data)

        self.assertEqual(result.features, [])
        self.assertEqual(result.modules, ['dashboard'])

    def test_schema_with_single_feature_is_valid(self):
        data = UpdateAdminRoleFeaturesSchema(feature_keys=['admin.tenants.view'])
        self.mock_repo.update_features.return_value = _role(features=['admin.tenants.view'])

        result = self.use_case.execute(ROLE_ID, data)

        self.assertEqual(len(result.features), 1)
