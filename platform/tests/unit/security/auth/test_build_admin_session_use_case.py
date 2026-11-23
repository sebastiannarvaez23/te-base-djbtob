"""
Unit tests for BuildAdminSessionUseCase and admin build_menu.

Uses the admin catalog (admin_modules / admin_features), not security_*.
No database required.
"""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch

from platform.features.security.auth.auth.application.use_cases import BuildAdminSessionUseCase
from platform.features.security.auth.auth.domain.schemas import AdminMenuItemSchema
from platform.features.security.auth.auth.infrastructure.repositories import (
    DjangoAdminSessionRepository,
)


def _menu_item(**overrides) -> AdminMenuItemSchema:
    defaults = dict(
        id=str(uuid.uuid4()),
        code='tenants',
        name='sidebar.tenants',
        icon='bx-buildings',
        route='/admin/tenants',
        section='platform',
    )
    defaults.update(overrides)
    return AdminMenuItemSchema(**defaults)


def _make_user(*, has_role=True, is_superuser=False):
    user = MagicMock()
    user.id = uuid.uuid4()
    user.username = 'admin1'
    user.is_superuser = is_superuser
    if has_role:
        role = MagicMock()
        role.id = uuid.uuid4()
        role.name = 'Operator'
        role.is_active = True
        user.role = role
        user.role_id = role.id
    else:
        user.role = None
        user.role_id = None
    return user


class TestBuildAdminSessionUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = BuildAdminSessionUseCase(self.mock_repo)
        idle_patch = patch(
            'platform.features.security.auth.auth.application.use_cases.inactivity_minutes',
            return_value=20,
        )
        self.idle_mock = idle_patch.start()
        self.addCleanup(idle_patch.stop)

    def test_returns_menu_features_and_inactivity_minutes(self):
        user = _make_user()
        menu = [_menu_item()]
        features = ['admin.tenants.view']
        self.mock_repo.build_menu.return_value = (menu, features)

        result = self.use_case.execute(user)

        self.mock_repo.build_menu.assert_called_once_with(user.role, is_superuser=False)
        self.assertEqual(result.menu, menu)
        self.assertEqual(result.features, features)
        self.assertEqual(result.inactivity_minutes, 20)
        self.idle_mock.assert_called_once_with(user_type='admin')

    def test_superuser_passes_flag_to_repository(self):
        user = _make_user(is_superuser=True)
        self.mock_repo.build_menu.return_value = ([], [])

        self.use_case.execute(user)

        self.mock_repo.build_menu.assert_called_once_with(user.role, is_superuser=True)

    def test_user_without_role_passes_none(self):
        user = _make_user(has_role=False)
        self.mock_repo.build_menu.return_value = ([], [])

        result = self.use_case.execute(user)

        self.mock_repo.build_menu.assert_called_once_with(None, is_superuser=False)
        self.assertEqual(result.menu, [])
        self.assertEqual(result.features, [])
        self.assertEqual(result.inactivity_minutes, 20)


class TestDjangoAdminSessionRepositoryBuildMenu(TestCase):

    def test_no_role_returns_empty(self):
        menu, features = DjangoAdminSessionRepository().build_menu(None)
        self.assertEqual(menu, [])
        self.assertEqual(features, [])

    @patch(
        'core.module_codes.admin_module_catalog_index',
        return_value={'tenants': 'tenants', 'dashboard': 'dashboard'},
    )
    @patch('platform.features.security.access.roles.models.AdminModule')
    @patch('platform.features.security.access.roles.models.AdminRoleModule')
    @patch('platform.features.security.access.roles.models.AdminRoleFeature')
    def test_role_features_and_modules_union(self, MockRF, MockRM, MockModule, _catalog):
        role = MagicMock()

        feature = MagicMock()
        feature.key = 'admin.tenants.view'
        feature.module.code = 'tenants'
        rf = MagicMock()
        rf.feature = feature

        tenants = MagicMock()
        tenants.id = uuid.uuid4()
        tenants.code = 'tenants'
        tenants.name = 'sidebar.tenants'
        tenants.icon = 'bx-buildings'
        tenants.route = '/admin/tenants'
        tenants.section.code = 'platform'
        tenants.section.name = 'Plataforma'
        tenants.section.order = 1
        tenants.order = 1

        dashboard = MagicMock()
        dashboard.id = uuid.uuid4()
        dashboard.code = 'dashboard'
        dashboard.name = 'sidebar.index'
        dashboard.icon = 'bx-grid-alt'
        dashboard.route = '/admin/dashboard'
        dashboard.section.code = 'none'
        dashboard.section.name = ''
        dashboard.section.order = 0
        dashboard.order = 1

        MockRF.objects.filter.return_value.select_related.return_value = [rf]
        MockRM.objects.filter.return_value.values_list.return_value = ['dashboard']
        MockModule.objects.filter.return_value.select_related.return_value = [tenants, dashboard]

        menu, features = DjangoAdminSessionRepository().build_menu(role)

        self.assertEqual(features, ['admin.tenants.view'])
        codes = [m.code for m in menu]
        self.assertIn('tenants', codes)
        self.assertIn('dashboard', codes)
        MockModule.objects.filter.assert_called_once()
        self.assertEqual(
            MockModule.objects.filter.call_args.kwargs['is_sidebar'],
            True,
        )
        self.assertTrue(MockModule.objects.filter.call_args.kwargs['is_active'])

    @patch('platform.features.security.access.roles.models.AdminFeature')
    @patch('platform.features.security.access.roles.models.AdminModule')
    def test_superuser_receives_full_admin_catalog(self, MockModule, MockFeature):
        module = MagicMock()
        module.id = uuid.uuid4()
        module.code = 'tenants'
        module.name = 'sidebar.tenants'
        module.icon = 'bx-buildings'
        module.route = '/admin/tenants'
        module.section.code = 'platform'
        module.section.name = 'Plataforma'

        MockModule.objects.filter.return_value.select_related.return_value.order_by.return_value = [module]
        MockFeature.objects.filter.return_value.order_by.return_value.values_list.return_value = [
            'admin.tenants.view',
        ]

        menu, features = DjangoAdminSessionRepository().build_menu(None, is_superuser=True)

        self.assertEqual(features, ['admin.tenants.view'])
        self.assertEqual(len(menu), 1)
        self.assertEqual(menu[0].code, 'tenants')
        self.assertEqual(menu[0].section_name, 'Plataforma')
        MockModule.objects.filter.assert_called_once_with(is_active=True, is_sidebar=True)
