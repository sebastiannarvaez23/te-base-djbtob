"""
Unit tests for Functionality use cases and access control:
  - ListFunctionalitiesPaginatedUseCase
  - GetFunctionalityUseCase
  - CreateFunctionalityUseCase
  - UpdateFunctionalityUseCase
  - DeleteFunctionalityUseCase
  - ToggleFunctionalityUseCase
  - AssignFunctionalityToModuleUseCase
  - Inactive functionality denied at access check level

No database required.
"""
import uuid
from datetime import datetime
from unittest import TestCase
from unittest.mock import MagicMock, patch

from platform.features.security.access.functionalities.application.use_cases import (
    AssignFunctionalityToModuleUseCase,
    CreateFunctionalityUseCase,
    DeleteFunctionalityUseCase,
    GetFunctionalityUseCase,
    ListFunctionalitiesPaginatedUseCase,
    ToggleFunctionalityUseCase,
    UpdateFunctionalityUseCase,
)
from platform.features.security.access.functionalities.domain.schemas import (
    AssignFunctionalitySchema,
    CreateFunctionalitySchema,
    FunctionalitySchema,
    UpdateFunctionalitySchema,
)
from core.errors import AppErrorCode, ConflictException
from core.query.core import PaginatedQuery, PaginatedResult


# ── Helper ─────────────────────────────────────────────────────────────────────

def _functionality(**overrides) -> FunctionalitySchema:
    defaults = dict(
        id=uuid.uuid4(),
        module='inventory',
        key='inventory.create',
        label='Crear inventario',
        category='features',
        is_active=True,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    defaults.update(overrides)
    return FunctionalitySchema(**defaults)


def _paginated_result(items, total=None, page=1, page_size=10):
    total = total or len(items)
    total_pages = (total + page_size - 1) // page_size if page_size else 1
    return PaginatedResult(
        items=items, total=total, page=page,
        page_size=page_size, total_pages=total_pages,
    )


# ── ListFunctionalitiesPaginatedUseCase ────────────────────────────────────────

class TestListFunctionalitiesPaginatedUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = ListFunctionalitiesPaginatedUseCase(self.mock_repo)

    def test_returns_paginated_functionalities(self):
        funcs = [_functionality(key='orders.create'), _functionality(key='orders.view')]
        result = _paginated_result(funcs, total=2)
        self.mock_repo.get_paginated.return_value = result

        query = MagicMock(spec=PaginatedQuery)
        response = self.use_case.execute(query)

        self.assertEqual(len(response.items), 2)
        self.assertEqual(response.total, 2)
        self.mock_repo.get_paginated.assert_called_once_with(query)

    def test_returns_empty_page_when_no_functionalities(self):
        result = _paginated_result([], total=0)
        self.mock_repo.get_paginated.return_value = result

        query = MagicMock(spec=PaginatedQuery)
        response = self.use_case.execute(query)

        self.assertEqual(response.items, [])
        self.assertEqual(response.total, 0)

    def test_pagination_metadata_is_correct(self):
        funcs = [_functionality() for _ in range(5)]
        result = _paginated_result(funcs, total=25, page=3, page_size=5)
        self.mock_repo.get_paginated.return_value = result

        query = MagicMock(spec=PaginatedQuery)
        response = self.use_case.execute(query)

        self.assertEqual(response.page, 3)
        self.assertEqual(response.page_size, 5)
        self.assertEqual(response.total_pages, 5)
        self.assertEqual(response.total, 25)


# ── GetFunctionalityUseCase ───────────────────────────────────────────────────

class TestGetFunctionalityUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = GetFunctionalityUseCase(self.mock_repo)

    def test_returns_functionality_by_id(self):
        func_id = uuid.uuid4()
        func = _functionality(id=func_id, key='orders.create')
        self.mock_repo.get_by_id.return_value = func

        result = self.use_case.execute(func_id)

        self.assertIsNotNone(result)
        self.assertEqual(result.id, func_id)
        self.assertEqual(result.key, 'orders.create')
        self.mock_repo.get_by_id.assert_called_once_with(func_id)

    def test_returns_none_when_not_found(self):
        self.mock_repo.get_by_id.return_value = None

        result = self.use_case.execute(uuid.uuid4())

        self.assertIsNone(result)

    def test_returns_inactive_functionality(self):
        func = _functionality(is_active=False)
        self.mock_repo.get_by_id.return_value = func

        result = self.use_case.execute(func.id)

        self.assertIsNotNone(result)
        self.assertFalse(result.is_active)


# ── CreateFunctionalityUseCase ────────────────────────────────────────────────

class TestCreateFunctionalityUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = CreateFunctionalityUseCase(self.mock_repo)
        self.exists_patcher = patch(
            'platform.features.security.access.functionalities.application.use_cases.Functionality'
        )
        self.mock_functionality = self.exists_patcher.start()
        self.mock_functionality.objects.filter.return_value.exists.return_value = False

    def tearDown(self):
        self.exists_patcher.stop()

    def test_creates_functionality_and_returns_schema(self):
        data = CreateFunctionalitySchema(module='inventory', key='inventory.create', label='Crear inventario')
        created = _functionality(key='inventory.create', label='Crear inventario')
        self.mock_repo.create.return_value = created

        result = self.use_case.execute(data)

        self.mock_repo.create.assert_called_once_with(data)
        self.assertEqual(result.key, 'inventory.create')
        self.assertEqual(result.label, 'Crear inventario')

    def test_default_category_is_features(self):
        data = CreateFunctionalitySchema(module='orders', key='orders.view', label='Ver Pedidos')
        created = _functionality(key='orders.view', category='features')
        self.mock_repo.create.return_value = created

        result = self.use_case.execute(data)

        self.assertEqual(result.category, 'features')

    def test_creates_with_custom_category(self):
        data = CreateFunctionalitySchema(module='reports', key='reports.export', label='Exportar', category='reports')
        created = _functionality(key='reports.export', category='reports')
        self.mock_repo.create.return_value = created

        result = self.use_case.execute(data)

        self.assertEqual(result.category, 'reports')

    def test_is_active_by_default(self):
        data = CreateFunctionalitySchema(module='orders', key='orders.new', label='Nueva Pedidos')
        self.mock_repo.create.return_value = _functionality(is_active=True)

        result = self.use_case.execute(data)

        self.assertTrue(result.is_active)

    def test_raises_conflict_when_key_already_exists(self):
        self.mock_functionality.objects.filter.return_value.exists.return_value = True
        data = CreateFunctionalitySchema(module='orders', key='orders.create', label='Crear Pedidos')

        with self.assertRaises(ConflictException) as ctx:
            self.use_case.execute(data)

        self.assertEqual(ctx.exception.code, AppErrorCode.FUNC_DUPLICATE_KEY)
        self.mock_repo.create.assert_not_called()


# ── UpdateFunctionalityUseCase ────────────────────────────────────────────────

class TestUpdateFunctionalityUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = UpdateFunctionalityUseCase(self.mock_repo)
        self.func_id = uuid.uuid4()
        self.exists_patcher = patch(
            'platform.features.security.access.functionalities.application.use_cases.Functionality'
        )
        self.mock_functionality = self.exists_patcher.start()
        self.mock_qs = MagicMock()
        self.mock_qs.exists.return_value = False
        self.mock_qs.exclude.return_value = self.mock_qs
        self.mock_functionality.objects.filter.return_value = self.mock_qs

    def tearDown(self):
        self.exists_patcher.stop()

    def test_updates_label(self):
        data = UpdateFunctionalitySchema(label='Etiqueta nueva')
        updated = _functionality(id=self.func_id, label='Etiqueta nueva')
        self.mock_repo.update.return_value = updated

        result = self.use_case.execute(self.func_id, data)

        self.mock_repo.update.assert_called_once_with(self.func_id, data)
        self.assertEqual(result.label, 'Etiqueta nueva')

    def test_updates_key(self):
        data = UpdateFunctionalitySchema(key='orders.edit')
        updated = _functionality(id=self.func_id, key='orders.edit')
        self.mock_repo.update.return_value = updated

        result = self.use_case.execute(self.func_id, data)

        self.assertEqual(result.key, 'orders.edit')

    def test_updates_module(self):
        data = UpdateFunctionalitySchema(module='sales')
        updated = _functionality(id=self.func_id, module='sales')
        self.mock_repo.update.return_value = updated

        result = self.use_case.execute(self.func_id, data)

        self.assertEqual(result.module, 'sales')

    def test_updates_category(self):
        data = UpdateFunctionalitySchema(category='admin')
        updated = _functionality(id=self.func_id, category='admin')
        self.mock_repo.update.return_value = updated

        result = self.use_case.execute(self.func_id, data)

        self.assertEqual(result.category, 'admin')

    def test_returns_none_when_not_found(self):
        data = UpdateFunctionalitySchema(label='x')
        self.mock_repo.update.return_value = None

        result = self.use_case.execute(uuid.uuid4(), data)

        self.assertIsNone(result)

    def test_partial_update_preserves_other_fields(self):
        data = UpdateFunctionalitySchema(label='Solo label')
        original = _functionality(id=self.func_id, key='orders.create', module='orders', category='features')
        updated = _functionality(id=self.func_id, key='orders.create', module='orders', category='features', label='Solo label')
        self.mock_repo.update.return_value = updated

        result = self.use_case.execute(self.func_id, data)

        self.assertEqual(result.key, 'orders.create')
        self.assertEqual(result.module, 'orders')
        self.assertEqual(result.label, 'Solo label')


# ── DeleteFunctionalityUseCase ────────────────────────────────────────────────

class TestDeleteFunctionalityUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = DeleteFunctionalityUseCase(self.mock_repo)

    def test_deletes_functionality_and_returns_true(self):
        func_id = uuid.uuid4()
        self.mock_repo.delete.return_value = True

        result = self.use_case.execute(func_id)

        self.assertTrue(result)
        self.mock_repo.delete.assert_called_once_with(func_id)

    def test_returns_false_when_not_found(self):
        self.mock_repo.delete.return_value = False

        result = self.use_case.execute(uuid.uuid4())

        self.assertFalse(result)


# ── ToggleFunctionalityUseCase ────────────────────────────────────────────────

class TestToggleFunctionalityUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = ToggleFunctionalityUseCase(self.mock_repo)

    def test_toggles_active_to_inactive(self):
        func_id = uuid.uuid4()
        toggled = _functionality(id=func_id, is_active=False)
        self.mock_repo.toggle.return_value = toggled

        result = self.use_case.execute(func_id)

        self.assertFalse(result.is_active)
        self.mock_repo.toggle.assert_called_once_with(func_id)

    def test_toggles_inactive_to_active(self):
        func_id = uuid.uuid4()
        toggled = _functionality(id=func_id, is_active=True)
        self.mock_repo.toggle.return_value = toggled

        result = self.use_case.execute(func_id)

        self.assertTrue(result.is_active)

    def test_returns_none_when_not_found(self):
        self.mock_repo.toggle.return_value = None

        result = self.use_case.execute(uuid.uuid4())

        self.assertIsNone(result)


# ── AssignFunctionalityToModuleUseCase ────────────────────────────────────────

class TestAssignFunctionalityToModuleUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = AssignFunctionalityToModuleUseCase(self.mock_repo)

    def test_assigns_functionality_to_new_module(self):
        func_id = uuid.uuid4()
        data = AssignFunctionalitySchema(module='sales')
        assigned = _functionality(id=func_id, module='sales')
        self.mock_repo.assign_module.return_value = assigned

        result = self.use_case.execute(func_id, data)

        self.assertEqual(result.module, 'sales')
        self.mock_repo.assign_module.assert_called_once_with(func_id, data)

    def test_returns_none_when_functionality_not_found(self):
        data = AssignFunctionalitySchema(module='sales')
        self.mock_repo.assign_module.return_value = None

        result = self.use_case.execute(uuid.uuid4(), data)

        self.assertIsNone(result)

    def test_assigns_to_same_module_is_idempotent(self):
        func_id = uuid.uuid4()
        data = AssignFunctionalitySchema(module='inventory')
        assigned = _functionality(id=func_id, module='inventory')
        self.mock_repo.assign_module.return_value = assigned

        result = self.use_case.execute(func_id, data)

        self.assertEqual(result.module, 'inventory')


# ── Inactive functionality denied at access level ─────────────────────────────
# When a functionality is toggled inactive, the AccessChecker._load_features
# only loads features where functionality__is_active=True, so an inactive
# functionality won't appear in the cached feature set and will be denied
# with SUB_002 (feature_denied).

class TestInactiveFunctionalityAccessDenied(TestCase):
    """Verifies that deactivating a functionality blocks access at the
    subscription access control level (AccessChecker)."""

    @patch('core.access.catalog_status.diagnose_feature_key', return_value=None)
    @patch('core.access.checker.SubscriptionCache')
    def test_inactive_functionality_not_in_features_causes_denial(self, MockCache, _diagnose):
        from core.access.checker import AccessChecker
        from core.errors.codes import AppErrorCode

        company = MagicMock()
        company.id = uuid.uuid4()
        company_id = str(company.id)

        # Subscription exists
        MockCache.get_subscription_id.return_value = 'sub-123'
        # Feature set does NOT include the deactivated functionality
        MockCache.get_features.return_value = {'orders.view', 'orders.list'}
        MockCache.get_limits.return_value = {}

        result = AccessChecker.check_feature(company, 'orders.create')

        self.assertFalse(result.is_allowed)
        self.assertEqual(result.error_code, AppErrorCode.SUB_FEATURE_DENIED)

    @patch('core.access.checker.SubscriptionCache')
    def test_active_functionality_in_features_allows_access(self, MockCache):
        from core.access.checker import AccessChecker

        company = MagicMock()
        company.id = uuid.uuid4()

        MockCache.get_subscription_id.return_value = 'sub-123'
        MockCache.get_features.return_value = {'orders.create', 'orders.view'}
        MockCache.get_limits.return_value = {}

        result = AccessChecker.check_feature(company, 'orders.create')

        self.assertTrue(result.is_allowed)

    @patch('core.access.catalog_status.diagnose_feature_key', return_value=None)
    @patch('core.access.checker.SubscriptionCache')
    def test_toggling_functionality_off_removes_from_login_response(self, MockCache, _diagnose):
        """When a functionality is inactive, _load_features filters it out
        (functionality__is_active=True), so it won't appear in the feature
        set returned during login — effectively hiding it from the UI."""
        from core.access.checker import AccessChecker
        from core.errors.codes import AppErrorCode

        company = MagicMock()
        company.id = uuid.uuid4()

        MockCache.get_subscription_id.return_value = 'sub-123'
        # Simulating that the feature was removed from the set after toggle
        MockCache.get_features.return_value = set()
        MockCache.get_limits.return_value = {}

        result = AccessChecker.check_feature(company, 'inventory.create')

        self.assertFalse(result.is_allowed)
        self.assertEqual(result.error_code, AppErrorCode.SUB_FEATURE_DENIED)
        self.assertIn('inventory.create', result.detail)
