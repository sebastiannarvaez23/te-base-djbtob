"""
Unit tests for client roles and permissions use cases:
  - ListRolesUseCase          → lista de roles por empresa
  - CreateRoleUseCase         → creación de rol
  - UpdateRoleUseCase         → actualización de rol
  - DeleteRoleUseCase         → eliminación de rol
  - ListFeaturesUseCase       → catálogo global de features/permisos
  - UpdateRoleFeaturesUseCase → asignación de permisos a un rol
  - ToggleCompanyRolAccessUseCase → activar/desactivar acceso de rol por empresa

No se requiere base de datos — los repositorios se reemplazan con Mocks.
"""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock, call

from client.features.security.access.roles.application.use_cases import (
    CreateRoleUseCase,
    DeleteRoleUseCase,
    ListFeaturesUseCase,
    ListRolesUseCase,
    ToggleCompanyRolAccessUseCase,
    UpdateRoleFeaturesUseCase,
    UpdateRoleUseCase,
)
from client.features.security.access.roles.domain.schemas import (
    CreateRoleSchema,
    FeatureSchema,
    RoleSchema,
    UpdateRoleFeaturesSchema,
    UpdateRoleSchema,
)
from core.query.core import PaginatedQuery, PaginatedResult


# ── Helpers ────────────────────────────────────────────────────────────────────

def _query(**filters) -> PaginatedQuery:
    return PaginatedQuery(page=0, page_size=0, filters=filters, unpaginated=True)


def _paginated(items) -> PaginatedResult:
    return PaginatedResult(items=items, total=len(items), page=0, page_size=0, total_pages=1)

def _feature(**overrides) -> FeatureSchema:
    defaults = dict(
        key='warehouse.orders.view',
        module='warehouse',
        label='Ver Pedidos',
        category='access',
    )
    defaults.update(overrides)
    return FeatureSchema(**defaults)


def _role(**overrides) -> RoleSchema:
    defaults = dict(
        id=uuid.uuid4(),
        name='Operador',
        description='Rol de operador de bodega',
        is_active=True,
        is_generic=False,
        is_editable=True,
        features=[],
    )
    defaults.update(overrides)
    return RoleSchema(**defaults)


COMPANY_ID = uuid.uuid4()
ROLE_ID = uuid.uuid4()


# ── ListRolesUseCase ───────────────────────────────────────────────────────────

class TestListRolesUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = ListRolesUseCase(self.mock_repo)

    def test_returns_roles_for_a_company(self):
        roles = [_role(name='Supervisor'), _role(name='Operador')]
        query = _query()
        self.mock_repo.get_all.return_value = _paginated(roles)

        result = self.use_case.execute(COMPANY_ID, query)

        self.assertEqual(len(result.items), 2)
        self.mock_repo.get_all.assert_called_once_with(COMPANY_ID, query)

    def test_returns_empty_list_when_company_has_no_roles(self):
        query = _query()
        self.mock_repo.get_all.return_value = _paginated([])

        result = self.use_case.execute(COMPANY_ID, query)

        self.assertEqual(result.items, [])

    def test_passes_company_id_to_repository(self):
        company_id = uuid.uuid4()
        query = _query()
        self.mock_repo.get_all.return_value = _paginated([])

        self.use_case.execute(company_id, query)

        self.mock_repo.get_all.assert_called_once_with(company_id, query)

    def test_returns_generic_roles_included_in_company_listing(self):
        generic_role = _role(name='Visitante', is_generic=True)
        company_role = _role(name='Supervisor', is_generic=False)
        query = _query()
        self.mock_repo.get_all.return_value = _paginated([generic_role, company_role])

        result = self.use_case.execute(COMPANY_ID, query)

        names = [r.name for r in result.items]
        self.assertIn('Visitante', names)
        self.assertIn('Supervisor', names)

    def test_roles_include_feature_keys(self):
        role_with_features = _role(features=['warehouse.orders.view', 'warehouse.picking.create'])
        query = _query()
        self.mock_repo.get_all.return_value = _paginated([role_with_features])

        result = self.use_case.execute(COMPANY_ID, query)

        self.assertIn('warehouse.orders.view', result.items[0].features)
        self.assertIn('warehouse.picking.create', result.items[0].features)

    def test_different_companies_receive_their_own_roles(self):
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()
        query = _query()
        roles_a = _paginated([_role(name='Admin A')])
        roles_b = _paginated([_role(name='Admin B'), _role(name='Operador B')])
        self.mock_repo.get_all.side_effect = (
            lambda cid, q: roles_a if cid == company_a else roles_b
        )

        result_a = self.use_case.execute(company_a, query)
        result_b = self.use_case.execute(company_b, query)

        self.assertEqual(len(result_a.items), 1)
        self.assertEqual(len(result_b.items), 2)


# ── CreateRoleUseCase ──────────────────────────────────────────────────────────

class TestCreateRoleUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = CreateRoleUseCase(self.mock_repo)

    def test_delegates_creation_to_repository(self):
        data = CreateRoleSchema(name='Auditor', company_id=COMPANY_ID)
        created = _role(name='Auditor')
        self.mock_repo.create.return_value = created

        result = self.use_case.execute(data)

        self.mock_repo.create.assert_called_once_with(data)
        self.assertEqual(result.name, 'Auditor')

    def test_new_role_is_active_by_default(self):
        data = CreateRoleSchema(name='Nuevo', company_id=COMPANY_ID)
        self.mock_repo.create.return_value = _role(is_active=True)

        result = self.use_case.execute(data)

        self.assertTrue(result.is_active)

    def test_new_role_starts_without_features(self):
        data = CreateRoleSchema(name='Sin permisos', company_id=COMPANY_ID)
        self.mock_repo.create.return_value = _role(features=[])

        result = self.use_case.execute(data)

        self.assertEqual(result.features, [])

    def test_new_role_is_not_generic(self):
        data = CreateRoleSchema(name='Empresa', company_id=COMPANY_ID)
        self.mock_repo.create.return_value = _role(is_generic=False)

        result = self.use_case.execute(data)

        self.assertFalse(result.is_generic)

    def test_company_id_is_forwarded_in_schema(self):
        company_id = uuid.uuid4()
        data = CreateRoleSchema(name='Test', company_id=company_id)
        self.mock_repo.create.return_value = _role()

        self.use_case.execute(data)

        called_schema = self.mock_repo.create.call_args[0][0]
        self.assertEqual(called_schema.company_id, company_id)

    def test_repository_exception_propagates(self):
        data = CreateRoleSchema(name='Error', company_id=COMPANY_ID)
        self.mock_repo.create.side_effect = ValueError('nombre duplicado')

        with self.assertRaises(ValueError):
            self.use_case.execute(data)


# ── UpdateRoleUseCase ──────────────────────────────────────────────────────────

class TestUpdateRoleUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = UpdateRoleUseCase(self.mock_repo)

    def test_updates_role_name(self):
        data = UpdateRoleSchema(name='Supervisor Senior')
        updated = _role(id=ROLE_ID, name='Supervisor Senior')
        self.mock_repo.update.return_value = updated

        result = self.use_case.execute(ROLE_ID, COMPANY_ID, data)

        self.assertEqual(result.name, 'Supervisor Senior')
        self.mock_repo.update.assert_called_once_with(ROLE_ID, COMPANY_ID, data)

    def test_can_deactivate_a_role(self):
        data = UpdateRoleSchema(is_active=False)
        self.mock_repo.update.return_value = _role(is_active=False)

        result = self.use_case.execute(ROLE_ID, COMPANY_ID, data)

        self.assertFalse(result.is_active)

    def test_can_reactivate_a_role(self):
        data = UpdateRoleSchema(is_active=True)
        self.mock_repo.update.return_value = _role(is_active=True)

        result = self.use_case.execute(ROLE_ID, COMPANY_ID, data)

        self.assertTrue(result.is_active)

    def test_returns_none_when_role_does_not_exist(self):
        self.mock_repo.update.return_value = None

        result = self.use_case.execute(uuid.uuid4(), COMPANY_ID, UpdateRoleSchema())

        self.assertIsNone(result)

    def test_returns_none_when_role_belongs_to_different_company(self):
        other_company = uuid.uuid4()
        self.mock_repo.update.return_value = None

        result = self.use_case.execute(ROLE_ID, other_company, UpdateRoleSchema(name='X'))

        self.assertIsNone(result)

    def test_partial_update_only_changes_provided_fields(self):
        data = UpdateRoleSchema(description='Nueva descripción')
        original = _role(id=ROLE_ID, name='Operador', description='Nueva descripción')
        self.mock_repo.update.return_value = original

        result = self.use_case.execute(ROLE_ID, COMPANY_ID, data)

        self.assertEqual(result.description, 'Nueva descripción')
        self.assertEqual(result.name, 'Operador')


# ── DeleteRoleUseCase ──────────────────────────────────────────────────────────

class TestDeleteRoleUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = DeleteRoleUseCase(self.mock_repo)

    def test_returns_true_when_role_is_deleted(self):
        self.mock_repo.delete.return_value = True

        result = self.use_case.execute(ROLE_ID, COMPANY_ID)

        self.assertTrue(result)
        self.mock_repo.delete.assert_called_once_with(ROLE_ID, COMPANY_ID)

    def test_returns_false_when_role_does_not_exist(self):
        self.mock_repo.delete.return_value = False

        result = self.use_case.execute(uuid.uuid4(), COMPANY_ID)

        self.assertFalse(result)

    def test_returns_false_when_role_belongs_to_different_company(self):
        other_company = uuid.uuid4()
        self.mock_repo.delete.return_value = False

        result = self.use_case.execute(ROLE_ID, other_company)

        self.assertFalse(result)

    def test_passes_both_ids_to_repository(self):
        role_id = uuid.uuid4()
        company_id = uuid.uuid4()
        self.mock_repo.delete.return_value = True

        self.use_case.execute(role_id, company_id)

        self.mock_repo.delete.assert_called_once_with(role_id, company_id)


# ── ListFeaturesUseCase (catálogo global de permisos) ─────────────────────────

class TestListFeaturesUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = ListFeaturesUseCase(self.mock_repo)

    def test_returns_all_available_features(self):
        features = [
            _feature(key='warehouse.orders.view', module='warehouse'),
            _feature(key='warehouse.picking.create', module='warehouse'),
            _feature(key='billing.invoices.view', module='billing'),
        ]
        query = _query()
        self.mock_repo.get_all_features.return_value = _paginated(features)

        result = self.use_case.execute(query)

        self.assertEqual(len(result.items), 3)
        self.mock_repo.get_all_features.assert_called_once_with(query, None)

    def test_returns_empty_list_when_no_features_configured(self):
        query = _query()
        self.mock_repo.get_all_features.return_value = _paginated([])

        result = self.use_case.execute(query)

        self.assertEqual(result.items, [])

    def test_features_include_module_and_label(self):
        feature = _feature(key='orders.view', module='orders', label='Ver Pedidos', category='access')
        query = _query()
        self.mock_repo.get_all_features.return_value = _paginated([feature])

        result = self.use_case.execute(query)

        self.assertEqual(result.items[0].module, 'orders')
        self.assertEqual(result.items[0].label, 'Ver Pedidos')
        self.assertEqual(result.items[0].category, 'access')

    def test_features_list_without_company_hides_complements(self):
        """Sin empresa el catálogo es el de plataforma: no incluye complementos."""
        query = _query()
        self.mock_repo.get_all_features.return_value = _paginated([])

        self.use_case.execute(query)

        self.mock_repo.get_all_features.assert_called_once_with(query, None)

    def test_features_list_passes_company_when_present(self):
        query = _query()
        company_id = uuid.uuid4()
        self.mock_repo.get_all_features.return_value = _paginated([])

        self.use_case.execute(query, company_id)

        self.mock_repo.get_all_features.assert_called_once_with(query, company_id)

    def test_returns_features_across_multiple_modules(self):
        features = [
            _feature(key='w.orders.view', module='warehouse'),
            _feature(key='b.invoice.view', module='billing'),
            _feature(key='s.users.list', module='security'),
        ]
        query = _query()
        self.mock_repo.get_all_features.return_value = _paginated(features)

        result = self.use_case.execute(query)

        modules = {f.module for f in result.items}
        self.assertEqual(modules, {'warehouse', 'billing', 'security'})


# ── UpdateRoleFeaturesUseCase (asignación de permisos) ────────────────────────

class TestUpdateRoleFeaturesUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = UpdateRoleFeaturesUseCase(self.mock_repo)

    def test_assigns_feature_keys_to_role(self):
        keys = ['warehouse.orders.view', 'warehouse.picking.create']
        data = UpdateRoleFeaturesSchema(feature_keys=keys)
        updated_role = _role(id=ROLE_ID, features=keys)
        self.mock_repo.update_features.return_value = updated_role

        result = self.use_case.execute(ROLE_ID, COMPANY_ID, data)

        self.mock_repo.update_features.assert_called_once_with(ROLE_ID, COMPANY_ID, data)
        self.assertEqual(result.features, keys)

    def test_clears_all_features_when_empty_list_provided(self):
        data = UpdateRoleFeaturesSchema(feature_keys=[])
        self.mock_repo.update_features.return_value = _role(features=[])

        result = self.use_case.execute(ROLE_ID, COMPANY_ID, data)

        self.assertEqual(result.features, [])

    def test_replaces_previous_features_completely(self):
        """La actualización es un reemplazo total, no una adición parcial."""
        old_keys = ['warehouse.orders.view']
        new_keys = ['billing.invoice.view', 'security.users.list']
        data = UpdateRoleFeaturesSchema(feature_keys=new_keys)
        self.mock_repo.update_features.return_value = _role(features=new_keys)

        result = self.use_case.execute(ROLE_ID, COMPANY_ID, data)

        self.assertNotIn(old_keys[0], result.features)
        self.assertIn('billing.invoice.view', result.features)

    def test_returns_none_when_role_does_not_exist(self):
        data = UpdateRoleFeaturesSchema(feature_keys=['any.feature'])
        self.mock_repo.update_features.return_value = None

        result = self.use_case.execute(uuid.uuid4(), COMPANY_ID, data)

        self.assertIsNone(result)

    def test_returns_none_when_role_belongs_to_different_company(self):
        data = UpdateRoleFeaturesSchema(feature_keys=['any.feature'])
        self.mock_repo.update_features.return_value = None

        result = self.use_case.execute(ROLE_ID, uuid.uuid4(), data)

        self.assertIsNone(result)

    def test_schema_with_single_feature_is_valid(self):
        data = UpdateRoleFeaturesSchema(feature_keys=['orders.view'])
        self.mock_repo.update_features.return_value = _role(features=['orders.view'])

        result = self.use_case.execute(ROLE_ID, COMPANY_ID, data)

        self.assertEqual(len(result.features), 1)


# ── ToggleCompanyRolAccessUseCase (acceso de rol por empresa) ─────────────────

class TestToggleCompanyRolAccessUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = ToggleCompanyRolAccessUseCase(self.mock_repo)

    def test_grants_access_to_role_for_company(self):
        self.mock_repo.toggle_company_access.return_value = _role(id=ROLE_ID, is_active=True)

        result = self.use_case.execute(ROLE_ID, COMPANY_ID, is_active=True)

        self.assertTrue(result.is_active)
        self.mock_repo.toggle_company_access.assert_called_once_with(ROLE_ID, COMPANY_ID, True)

    def test_revokes_access_to_role_for_company(self):
        self.mock_repo.toggle_company_access.return_value = _role(id=ROLE_ID, is_active=False)

        result = self.use_case.execute(ROLE_ID, COMPANY_ID, is_active=False)

        self.assertFalse(result.is_active)
        self.mock_repo.toggle_company_access.assert_called_once_with(ROLE_ID, COMPANY_ID, False)

    def test_returns_none_when_role_not_found(self):
        self.mock_repo.toggle_company_access.return_value = None

        result = self.use_case.execute(uuid.uuid4(), COMPANY_ID, is_active=True)

        self.assertIsNone(result)

    def test_returns_none_when_company_does_not_have_this_role(self):
        self.mock_repo.toggle_company_access.return_value = None

        result = self.use_case.execute(ROLE_ID, uuid.uuid4(), is_active=False)

        self.assertIsNone(result)

    def test_granting_access_to_already_active_role_is_idempotent(self):
        """Activar un rol ya activo no debe fallar — el repo simplemente confirma el estado."""
        self.mock_repo.toggle_company_access.return_value = _role(is_active=True)

        result = self.use_case.execute(ROLE_ID, COMPANY_ID, is_active=True)

        self.assertTrue(result.is_active)

    def test_revoking_access_to_already_inactive_role_is_idempotent(self):
        self.mock_repo.toggle_company_access.return_value = _role(is_active=False)

        result = self.use_case.execute(ROLE_ID, COMPANY_ID, is_active=False)

        self.assertFalse(result.is_active)

    def test_passes_is_active_false_explicitly(self):
        self.mock_repo.toggle_company_access.return_value = _role(is_active=False)

        self.use_case.execute(ROLE_ID, COMPANY_ID, is_active=False)

        _, _, passed_flag = self.mock_repo.toggle_company_access.call_args[0]
        self.assertFalse(passed_flag)

    def test_different_companies_can_independently_control_same_role(self):
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()
        self.mock_repo.toggle_company_access.side_effect = [
            _role(is_active=True),
            _role(is_active=False),
        ]

        result_a = self.use_case.execute(ROLE_ID, company_a, is_active=True)
        result_b = self.use_case.execute(ROLE_ID, company_b, is_active=False)

        self.assertTrue(result_a.is_active)
        self.assertFalse(result_b.is_active)
        self.assertEqual(self.mock_repo.toggle_company_access.call_count, 2)
