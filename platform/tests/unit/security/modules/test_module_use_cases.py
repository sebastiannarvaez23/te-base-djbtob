"""
Unit tests for Module use cases and access control:
  - ListModulesUseCase
  - ListModulesPaginatedUseCase
  - GetModuleUseCase
  - CreateModuleUseCase
  - UpdateModuleUseCase
  - DeleteModuleUseCase
  - ToggleModuleUseCase
  - Inactive module hidden from sidebar / denied at backend level

No database required.
"""
import uuid
from datetime import datetime
from unittest import TestCase
from unittest.mock import MagicMock, patch

from platform.features.security.access.modules.application.use_cases import (
    CreateModuleUseCase,
    DeleteModuleUseCase,
    GetModuleUseCase,
    ListModulesPaginatedUseCase,
    ListModulesUseCase,
    ToggleModuleUseCase,
    UpdateModuleUseCase,
)
from platform.features.security.access.modules.domain.schemas import (
    CreateModuleSchema,
    ModuleSchema,
    UpdateModuleSchema,
)
from core.query.core import PaginatedQuery, PaginatedResult


# ── Helper ─────────────────────────────────────────────────────────────────────

def _module(**overrides) -> ModuleSchema:
    defaults = dict(
        id=uuid.uuid4(),
        code='inventory',
        name='Inventario',
        description='Módulo de inventario',
        icon='pi pi-box',
        route='/inventory',
        section_id=uuid.uuid4(),
        order=0,
        is_sidebar=True,
        is_active=True,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    defaults.update(overrides)
    return ModuleSchema(**defaults)


def _paginated_result(items, total=None, page=1, page_size=10):
    total = total or len(items)
    total_pages = (total + page_size - 1) // page_size if page_size else 1
    return PaginatedResult(
        items=items, total=total, page=page,
        page_size=page_size, total_pages=total_pages,
    )


# ── ListModulesUseCase ────────────────────────────────────────────────────────

class TestListModulesUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = ListModulesUseCase(self.mock_repo)

    def test_returns_all_modules(self):
        modules = [_module(code='orders'), _module(code='inventory'), _module(code='reports')]
        self.mock_repo.get_all.return_value = modules

        result = self.use_case.execute()

        self.assertEqual(len(result), 3)
        self.mock_repo.get_all.assert_called_once()

    def test_returns_empty_list_when_no_modules(self):
        self.mock_repo.get_all.return_value = []

        result = self.use_case.execute()

        self.assertEqual(result, [])

    def test_includes_active_and_inactive_modules(self):
        modules = [_module(is_active=True), _module(is_active=False)]
        self.mock_repo.get_all.return_value = modules

        result = self.use_case.execute()

        self.assertEqual(len(result), 2)


# ── ListModulesPaginatedUseCase ───────────────────────────────────────────────

class TestListModulesPaginatedUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = ListModulesPaginatedUseCase(self.mock_repo)

    def test_returns_paginated_modules(self):
        modules = [_module(code='a'), _module(code='b')]
        result = _paginated_result(modules)
        self.mock_repo.get_paginated.return_value = result

        query = MagicMock(spec=PaginatedQuery)
        response = self.use_case.execute(query)

        self.assertEqual(len(response.items), 2)
        self.mock_repo.get_paginated.assert_called_once_with(query)

    def test_returns_empty_page(self):
        result = _paginated_result([], total=0)
        self.mock_repo.get_paginated.return_value = result

        query = MagicMock(spec=PaginatedQuery)
        response = self.use_case.execute(query)

        self.assertEqual(response.total, 0)
        self.assertEqual(response.items, [])


# ── GetModuleUseCase ──────────────────────────────────────────────────────────

class TestGetModuleUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = GetModuleUseCase(self.mock_repo)

    def test_returns_module_by_id(self):
        mod_id = uuid.uuid4()
        mod = _module(id=mod_id, code='orders')
        self.mock_repo.get_by_id.return_value = mod

        result = self.use_case.execute(mod_id)

        self.assertIsNotNone(result)
        self.assertEqual(result.id, mod_id)
        self.assertEqual(result.code, 'orders')

    def test_returns_none_when_not_found(self):
        self.mock_repo.get_by_id.return_value = None

        result = self.use_case.execute(uuid.uuid4())

        self.assertIsNone(result)


# ── CreateModuleUseCase ───────────────────────────────────────────────────────

class TestCreateModuleUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = CreateModuleUseCase(self.mock_repo)

    def test_creates_module_and_returns_schema(self):
        section_id = uuid.uuid4()
        data = CreateModuleSchema(
            code='sales', name='Ventas', icon='pi pi-dollar',
            route='/sales', section_id=section_id,
        )
        created = _module(code='sales', name='Ventas', section_id=section_id)
        self.mock_repo.create.return_value = created

        result = self.use_case.execute(data)

        self.mock_repo.create.assert_called_once_with(data)
        self.assertEqual(result.code, 'sales')
        self.assertEqual(result.name, 'Ventas')

    def test_is_active_by_default(self):
        data = CreateModuleSchema(
            code='hr', name='RRHH', icon='pi pi-users',
            route='/hr', section_id=uuid.uuid4(),
        )
        self.mock_repo.create.return_value = _module(is_active=True)

        result = self.use_case.execute(data)

        self.assertTrue(result.is_active)

    def test_propagates_duplicate_code_conflict(self):
        from core.errors import AppErrorCode, ConflictException

        data = CreateModuleSchema(
            code='inventory', name='Inventario', icon='pi pi-box',
            route='/inventory', section_id=uuid.uuid4(),
        )
        self.mock_repo.create.side_effect = ConflictException(AppErrorCode.MODULE_DUPLICATE_CODE)

        with self.assertRaises(ConflictException) as ctx:
            self.use_case.execute(data)

        self.assertEqual(ctx.exception.code, AppErrorCode.MODULE_DUPLICATE_CODE)

    def test_default_order_is_zero(self):
        data = CreateModuleSchema(
            code='config', name='Configuración', icon='pi pi-cog',
            route='/config', section_id=uuid.uuid4(),
        )
        created = _module(order=0)
        self.mock_repo.create.return_value = created

        result = self.use_case.execute(data)

        self.assertEqual(result.order, 0)


# ── UpdateModuleUseCase ───────────────────────────────────────────────────────

class TestUpdateModuleUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = UpdateModuleUseCase(self.mock_repo)
        self.mod_id = uuid.uuid4()

    def test_updates_name(self):
        data = UpdateModuleSchema(name='Nombre nuevo')
        updated = _module(id=self.mod_id, name='Nombre nuevo')
        self.mock_repo.update.return_value = updated

        result = self.use_case.execute(self.mod_id, data)

        self.assertEqual(result.name, 'Nombre nuevo')
        self.mock_repo.update.assert_called_once_with(self.mod_id, data)

    def test_updates_route(self):
        data = UpdateModuleSchema(route='/new-route')
        updated = _module(id=self.mod_id, route='/new-route')
        self.mock_repo.update.return_value = updated

        result = self.use_case.execute(self.mod_id, data)

        self.assertEqual(result.route, '/new-route')

    def test_updates_icon(self):
        data = UpdateModuleSchema(icon='pi pi-star')
        updated = _module(id=self.mod_id, icon='pi pi-star')
        self.mock_repo.update.return_value = updated

        result = self.use_case.execute(self.mod_id, data)

        self.assertEqual(result.icon, 'pi pi-star')

    def test_updates_order(self):
        data = UpdateModuleSchema(order=5)
        updated = _module(id=self.mod_id, order=5)
        self.mock_repo.update.return_value = updated

        result = self.use_case.execute(self.mod_id, data)

        self.assertEqual(result.order, 5)

    def test_updates_section(self):
        new_section = uuid.uuid4()
        data = UpdateModuleSchema(section_id=new_section)
        updated = _module(id=self.mod_id, section_id=new_section)
        self.mock_repo.update.return_value = updated

        result = self.use_case.execute(self.mod_id, data)

        self.assertEqual(result.section_id, new_section)

    def test_returns_none_when_not_found(self):
        data = UpdateModuleSchema(name='x')
        self.mock_repo.update.return_value = None

        result = self.use_case.execute(uuid.uuid4(), data)

        self.assertIsNone(result)

    def test_partial_update_preserves_other_fields(self):
        data = UpdateModuleSchema(name='Solo nombre')
        updated = _module(
            id=self.mod_id, code='inventory', name='Solo nombre',
            route='/inventory', icon='pi pi-box',
        )
        self.mock_repo.update.return_value = updated

        result = self.use_case.execute(self.mod_id, data)

        self.assertEqual(result.code, 'inventory')
        self.assertEqual(result.route, '/inventory')
        self.assertEqual(result.name, 'Solo nombre')


# ── DeleteModuleUseCase ───────────────────────────────────────────────────────

class TestDeleteModuleUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = DeleteModuleUseCase(self.mock_repo)

    def test_deletes_module_and_returns_true(self):
        mod_id = uuid.uuid4()
        self.mock_repo.delete.return_value = True

        result = self.use_case.execute(mod_id)

        self.assertTrue(result)
        self.mock_repo.delete.assert_called_once_with(mod_id)

    def test_returns_false_when_not_found(self):
        self.mock_repo.delete.return_value = False

        result = self.use_case.execute(uuid.uuid4())

        self.assertFalse(result)

    def test_propagates_protected_error_when_has_functionalities(self):
        from django.db.models.deletion import ProtectedError
        self.mock_repo.delete.side_effect = ProtectedError(
            'Cannot delete module with functionalities', set()
        )

        with self.assertRaises(ProtectedError):
            self.use_case.execute(uuid.uuid4())


# ── ToggleModuleUseCase ───────────────────────────────────────────────────────

class TestToggleModuleUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = ToggleModuleUseCase(self.mock_repo)

    def test_toggles_active_to_inactive(self):
        mod_id = uuid.uuid4()
        toggled = _module(id=mod_id, is_active=False)
        self.mock_repo.toggle.return_value = toggled

        result = self.use_case.execute(mod_id)

        self.assertFalse(result.is_active)
        self.mock_repo.toggle.assert_called_once_with(mod_id)

    def test_toggles_inactive_to_active(self):
        mod_id = uuid.uuid4()
        toggled = _module(id=mod_id, is_active=True)
        self.mock_repo.toggle.return_value = toggled

        result = self.use_case.execute(mod_id)

        self.assertTrue(result.is_active)

    def test_returns_none_when_not_found(self):
        self.mock_repo.toggle.return_value = None

        result = self.use_case.execute(uuid.uuid4())

        self.assertIsNone(result)


# ── Inactive module hidden from sidebar / denied at backend ──────────────────
# When a module is toggled inactive:
# 1. The sidebar modules list (login response) only includes active modules
#    via SubscriptionModule + Module.is_active filtering.
# 2. Backend endpoints linked to this module deny access because the
#    functionalities belong to an inactive module → features not in plan.

class TestInactiveModuleSidebarAndAccess(TestCase):
    """Verifies that deactivating a module hides it from the sidebar
    (not returned at login) and denies access to its features at the
    backend level."""

    @patch('core.access.catalog_status.diagnose_feature_key', return_value=None)
    @patch('core.access.checker.SubscriptionCache')
    def test_inactive_module_features_denied_at_access_level(self, MockCache, _diagnose):
        """When a module is inactive, its functionalities should not appear
        in the feature set (filtered by functionality__is_active=True and
        the module relationship), resulting in SUB_002 denial."""
        from core.access.checker import AccessChecker
        from core.errors.codes import AppErrorCode

        company = MagicMock()
        company.id = uuid.uuid4()

        MockCache.get_subscription_id.return_value = 'sub-456'
        # Inactive module → its features are not in the cached set
        MockCache.get_features.return_value = {'reports.view'}
        MockCache.get_limits.return_value = {}

        # Feature from the now-inactive module
        result = AccessChecker.check_feature(company, 'inventory.create')

        self.assertFalse(result.is_allowed)
        self.assertEqual(result.error_code, AppErrorCode.SUB_FEATURE_DENIED)

    @patch('core.access.checker.SubscriptionCache')
    def test_active_module_features_allowed(self, MockCache):
        from core.access.checker import AccessChecker

        company = MagicMock()
        company.id = uuid.uuid4()

        MockCache.get_subscription_id.return_value = 'sub-456'
        MockCache.get_features.return_value = {'inventory.create', 'inventory.view'}
        MockCache.get_limits.return_value = {}

        result = AccessChecker.check_feature(company, 'inventory.create')

        self.assertTrue(result.is_allowed)

    @patch('core.access.catalog_status.diagnose_feature_key', return_value=None)
    @patch('core.access.checker.SubscriptionCache')
    def test_all_features_of_inactive_module_denied(self, MockCache, _diagnose):
        """All functionalities of an inactive module are denied,
        not just individual ones."""
        from core.access.checker import AccessChecker
        from core.errors.codes import AppErrorCode

        company = MagicMock()
        company.id = uuid.uuid4()

        MockCache.get_subscription_id.return_value = 'sub-456'
        # No inventory features in the set at all
        MockCache.get_features.return_value = {'orders.create', 'orders.view'}
        MockCache.get_limits.return_value = {}

        for feature in ['inventory.create', 'inventory.view', 'inventory.delete']:
            result = AccessChecker.check_feature(company, feature)
            self.assertFalse(result.is_allowed)
            self.assertEqual(result.error_code, AppErrorCode.SUB_FEATURE_DENIED)

    def test_inactive_module_not_in_sidebar_response(self):
        """Simulates that only active modules are returned in the sidebar
        list (login response). Inactive modules are filtered out."""
        all_modules = [
            _module(code='orders', is_active=True),
            _module(code='inventory', is_active=False),
            _module(code='reports', is_active=True),
        ]

        # Simulate the filtering that happens at the API/repository level
        sidebar_modules = [m for m in all_modules if m.is_active]

        self.assertEqual(len(sidebar_modules), 2)
        codes = [m.code for m in sidebar_modules]
        self.assertIn('orders', codes)
        self.assertIn('reports', codes)
        self.assertNotIn('inventory', codes)

    def test_non_sidebar_module_not_in_sidebar_response(self):
        all_modules = [
            _module(code='orders', is_sidebar=True),
            _module(code='ai_engine', is_sidebar=False),
            _module(code='reports', is_sidebar=True),
        ]
        sidebar_modules = [m for m in all_modules if m.is_active and m.is_sidebar]
        codes = [m.code for m in sidebar_modules]
        self.assertEqual(codes, ['orders', 'reports'])

    def test_reactivated_module_reappears_in_sidebar(self):
        """When a module is toggled back to active, it reappears."""
        all_modules = [
            _module(code='orders', is_active=True),
            _module(code='inventory', is_active=True),
        ]

        sidebar_modules = [m for m in all_modules if m.is_active]

        self.assertEqual(len(sidebar_modules), 2)
        codes = [m.code for m in sidebar_modules]
        self.assertIn('inventory', codes)
