"""
Unit tests for admin platform use cases:
  - platform_auth  → AdminLoginUseCase
  - platform_roles → ListAdminRolesUseCase / CreateAdminRoleUseCase / UpdateAdminRoleUseCase / DeleteAdminRoleUseCase
                     ListAdminFeaturesUseCase / UpdateAdminRoleFeaturesUseCase
  - platform_users → ListAdminUsersPaginatedUseCase / GetAdminUserUseCase / CreateAdminUserUseCase
                     UpdateAdminUserUseCase / ToggleAdminUserActiveUseCase

No database required.
"""
import uuid
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock

_NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)

from platform.features.security.auth.auth.application.use_cases import AdminLoginUseCase
from platform.features.security.access.roles.application.use_cases import (
    ListAdminRolesUseCase,
    CreateAdminRoleUseCase,
    UpdateAdminRoleUseCase,
    DeleteAdminRoleUseCase,
    ListAdminFeaturesUseCase,
    UpdateAdminRoleFeaturesUseCase,
)
from platform.features.security.access.roles.domain.schemas import (
    AdminRoleSchema,
    CreateAdminRoleSchema,
    FeatureCatalogItemSchema,
    UpdateAdminRoleFeaturesSchema,
    UpdateAdminRoleSchema,
)
from platform.features.security.identity.users.application.use_cases import (
    ListAdminUsersPaginatedUseCase,
    GetAdminUserUseCase,
    CreateAdminUserUseCase,
    UpdateAdminUserUseCase,
    ToggleAdminUserActiveUseCase,
)
from platform.features.security.identity.users.domain.schemas import AdminUserSchema
from core.query.core import PaginatedQuery, PaginatedResult


# ── Helpers ────────────────────────────────────────────────────────────────────

def _role(**overrides) -> AdminRoleSchema:
    defaults = dict(
        id=uuid.uuid4(),
        name='Operator',
        description=None,
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


def _user(**overrides) -> AdminUserSchema:
    defaults = dict(
        id=uuid.uuid4(),
        username='admin1',
        email='admin@wa.com',
        first_name='Admin',
        last_name='User',
        telephone='',
        rol=_role(),
        is_active=True,
        is_superuser=False,
        last_login=None,
        created_at=_NOW,
        updated_at=_NOW,
    )
    defaults.update(overrides)
    return AdminUserSchema(**defaults)


# ── AdminLoginUseCase ──────────────────────────────────────────────────────────

class TestAdminLoginUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = AdminLoginUseCase(self.mock_repo)

    def test_successful_login_returns_user(self):
        user_mock = MagicMock()
        user_mock.username = 'admin1'
        self.mock_repo.authenticate.return_value = user_mock

        result = self.use_case.execute('admin1', 'pass1234')

        self.assertIsNotNone(result)
        self.assertEqual(result.username, 'admin1')

    def test_failed_login_returns_none(self):
        self.mock_repo.authenticate.return_value = None

        result = self.use_case.execute('admin1', 'wrong')

        self.assertIsNone(result)


# ── Role use cases ─────────────────────────────────────────────────────────────

class TestListAdminRolesUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = ListAdminRolesUseCase(self.mock_repo)

    def test_returns_list_of_roles(self):
        roles = [_role(name='Admin'), _role(name='Operator')]
        self.mock_repo.get_all.return_value = roles

        result = self.use_case.execute()

        self.assertEqual(len(result), 2)
        self.mock_repo.get_all.assert_called_once()

    def test_returns_empty_list_when_no_roles_exist(self):
        self.mock_repo.get_all.return_value = []

        result = self.use_case.execute()

        self.assertEqual(result, [])


class TestCreateAdminRoleUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = CreateAdminRoleUseCase(self.mock_repo)

    def test_delegates_creation_to_repository(self):
        data = CreateAdminRoleSchema(name='Supervisor', is_active=True)
        created_role = _role(name='Supervisor')
        self.mock_repo.create.return_value = created_role

        result = self.use_case.execute(data)

        self.mock_repo.create.assert_called_once_with(data)
        self.assertEqual(result.name, 'Supervisor')

    def test_created_role_is_active_by_default(self):
        data = CreateAdminRoleSchema(name='New Role', is_active=True)
        self.mock_repo.create.return_value = _role(is_active=True)

        result = self.use_case.execute(data)

        self.assertTrue(result.is_active)


class TestUpdateAdminRoleUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = UpdateAdminRoleUseCase(self.mock_repo)
        self.role_id = uuid.uuid4()

    def test_delegates_update_to_repository(self):
        data = UpdateAdminRoleSchema(name='Senior Supervisor')
        updated_role = _role(id=self.role_id, name='Senior Supervisor')
        self.mock_repo.update.return_value = updated_role

        result = self.use_case.execute(self.role_id, data)

        self.mock_repo.update.assert_called_once_with(self.role_id, data)
        self.assertEqual(result.name, 'Senior Supervisor')

    def test_returns_none_when_role_does_not_exist(self):
        self.mock_repo.update.return_value = None

        result = self.use_case.execute(uuid.uuid4(), UpdateAdminRoleSchema())

        self.assertIsNone(result)


class TestDeleteAdminRoleUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = DeleteAdminRoleUseCase(self.mock_repo)

    def test_returns_true_when_deletion_is_successful(self):
        role_id = uuid.uuid4()
        self.mock_repo.delete.return_value = True

        result = self.use_case.execute(role_id)

        self.assertTrue(result)
        self.mock_repo.delete.assert_called_once_with(role_id)

    def test_returns_false_when_role_does_not_exist(self):
        self.mock_repo.delete.return_value = False

        result = self.use_case.execute(uuid.uuid4())

        self.assertFalse(result)


class TestListAdminFeaturesUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = ListAdminFeaturesUseCase(self.mock_repo)

    def test_returns_feature_catalog(self):
        catalog = [
            FeatureCatalogItemSchema(key='orders.view', module='orders', label='View orders', category='features'),
        ]
        self.mock_repo.get_all_features.return_value = catalog

        result = self.use_case.execute()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].key, 'orders.view')


class TestUpdateAdminRoleFeaturesUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = UpdateAdminRoleFeaturesUseCase(self.mock_repo)
        self.role_id = uuid.uuid4()

    def test_delegates_update_to_repository(self):
        data = UpdateAdminRoleFeaturesSchema(feature_keys=['orders.view'], module_codes=['orders'])
        updated = _role(id=self.role_id, features=['orders.view'], modules=['orders'])
        self.mock_repo.update_features.return_value = updated

        result = self.use_case.execute(self.role_id, data)

        self.mock_repo.update_features.assert_called_once_with(self.role_id, data)
        self.assertEqual(result.features, ['orders.view'])
        self.assertEqual(result.modules, ['orders'])

    def test_returns_none_when_role_does_not_exist(self):
        self.mock_repo.update_features.return_value = None

        result = self.use_case.execute(
            uuid.uuid4(),
            UpdateAdminRoleFeaturesSchema(feature_keys=[], module_codes=[]),
        )

        self.assertIsNone(result)


# ── User use cases ─────────────────────────────────────────────────────────────

class TestListAdminUsersPaginatedUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = ListAdminUsersPaginatedUseCase(self.mock_repo)

    def test_returns_paginated_users(self):
        users = [_user(username='admin1'), _user(username='admin2')]
        query = PaginatedQuery(page=0, page_size=10, filters={})
        self.mock_repo.get_paginated.return_value = PaginatedResult(
            items=users, total=2, page=0, page_size=10, total_pages=1,
        )

        result = self.use_case.execute(query)

        self.assertEqual(len(result.items), 2)
        self.assertEqual(result.total, 2)
        self.mock_repo.get_paginated.assert_called_once_with(query)

    def test_returns_empty_list_when_no_users_exist(self):
        query = PaginatedQuery(page=0, page_size=10, filters={})
        self.mock_repo.get_paginated.return_value = PaginatedResult(
            items=[], total=0, page=0, page_size=10, total_pages=0,
        )

        result = self.use_case.execute(query)

        self.assertEqual(result.items, [])
        self.assertEqual(result.total, 0)


class TestGetAdminUserUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = GetAdminUserUseCase(self.mock_repo)

    def test_returns_user_by_id(self):
        user_id = uuid.uuid4()
        user = _user(id=user_id)
        self.mock_repo.get_by_id.return_value = user

        result = self.use_case.execute(user_id)

        self.mock_repo.get_by_id.assert_called_once_with(user_id)
        self.assertEqual(result.id, user_id)

    def test_returns_none_when_user_does_not_exist(self):
        self.mock_repo.get_by_id.return_value = None

        result = self.use_case.execute(uuid.uuid4())

        self.assertIsNone(result)


class TestToggleAdminUserActiveUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = ToggleAdminUserActiveUseCase(self.mock_repo)

    def test_toggles_user_and_returns_updated_schema(self):
        user_id = uuid.uuid4()
        inactive_user = _user(id=user_id, is_active=False)
        self.mock_repo.toggle_active.return_value = inactive_user

        result = self.use_case.execute(user_id)

        self.assertFalse(result.is_active)
        self.mock_repo.toggle_active.assert_called_once_with(user_id)

    def test_returns_none_when_user_does_not_exist(self):
        self.mock_repo.toggle_active.return_value = None

        result = self.use_case.execute(uuid.uuid4())

        self.assertIsNone(result)
