"""
Unit tests para los casos de uso del catálogo de features/permisos:
  - ListFeaturesUseCase   → listar features, opcionalmente filtradas por módulo
  - CreateFeatureUseCase  → crear nueva feature en el catálogo
  - UpdateFeatureUseCase  → actualizar label, categoría o estado de una feature

No se requiere base de datos.
"""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock

from client.features.security.access.features.application.use_cases import (
    CreateFeatureUseCase,
    ListFeaturesUseCase,
    UpdateFeatureUseCase,
)
from client.features.security.access.features.domain.schemas import (
    CreateFeatureSchema,
    FeatureSchema,
    UpdateFeatureSchema,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _feature(**overrides) -> FeatureSchema:
    defaults = dict(
        id=uuid.uuid4(),
        module='warehouse',
        key='warehouse.orders.view',
        label='Ver Pedidos',
        category='access',
        is_active=True,
    )
    defaults.update(overrides)
    return FeatureSchema(**defaults)


FEATURE_ID = uuid.uuid4()


# ── ListFeaturesUseCase ────────────────────────────────────────────────────────

class TestListFeaturesUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = ListFeaturesUseCase(self.mock_repo)

    def test_returns_all_features_when_no_module_filter(self):
        features = [
            _feature(key='warehouse.orders.view'),
            _feature(key='billing.invoice.view', module='billing'),
            _feature(key='security.users.list', module='security'),
        ]
        self.mock_repo.get_all.return_value = features

        result = self.use_case.execute()

        self.assertEqual(len(result), 3)
        self.mock_repo.get_all.assert_called_once_with(module=None)

    def test_returns_empty_list_when_no_features_exist(self):
        self.mock_repo.get_all.return_value = []

        result = self.use_case.execute()

        self.assertEqual(result, [])

    def test_filters_by_module_when_provided(self):
        warehouse_features = [
            _feature(key='warehouse.orders.view', module='warehouse'),
            _feature(key='warehouse.picking.create', module='warehouse'),
        ]
        self.mock_repo.get_all.return_value = warehouse_features

        result = self.use_case.execute(module='warehouse')

        self.mock_repo.get_all.assert_called_once_with(module='warehouse')
        self.assertEqual(len(result), 2)

    def test_returns_empty_list_when_module_has_no_features(self):
        self.mock_repo.get_all.return_value = []

        result = self.use_case.execute(module='nonexistent_module')

        self.assertEqual(result, [])

    def test_each_feature_has_required_fields(self):
        feature = _feature(
            module='billing',
            key='billing.invoice.create',
            label='Crear facturas',
            category='action',
            is_active=True,
        )
        self.mock_repo.get_all.return_value = [feature]

        result = self.use_case.execute()

        f = result[0]
        self.assertEqual(f.module, 'billing')
        self.assertEqual(f.key, 'billing.invoice.create')
        self.assertEqual(f.label, 'Crear facturas')
        self.assertEqual(f.category, 'action')
        self.assertTrue(f.is_active)

    def test_includes_inactive_features_in_listing(self):
        features = [
            _feature(key='f.active', is_active=True),
            _feature(key='f.inactive', is_active=False),
        ]
        self.mock_repo.get_all.return_value = features

        result = self.use_case.execute()

        is_active_values = [f.is_active for f in result]
        self.assertIn(True, is_active_values)
        self.assertIn(False, is_active_values)

    def test_features_from_multiple_modules_returned_without_filter(self):
        features = [
            _feature(module='warehouse'),
            _feature(module='billing'),
            _feature(module='security'),
        ]
        self.mock_repo.get_all.return_value = features

        result = self.use_case.execute()

        modules = {f.module for f in result}
        self.assertEqual(modules, {'warehouse', 'billing', 'security'})

    def test_billing_module_filter_does_not_return_warehouse_features(self):
        billing_features = [_feature(module='billing', key='billing.report.view')]
        self.mock_repo.get_all.return_value = billing_features

        result = self.use_case.execute(module='billing')

        for f in result:
            self.assertEqual(f.module, 'billing')


# ── CreateFeatureUseCase ───────────────────────────────────────────────────────

class TestCreateFeatureUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = CreateFeatureUseCase(self.mock_repo)

    def test_delegates_creation_to_repository(self):
        data = CreateFeatureSchema(
            module='warehouse',
            key='warehouse.dispatch.create',
            label='Crear despacho',
            category='action',
        )
        created = _feature(key='warehouse.dispatch.create', label='Crear despacho')
        self.mock_repo.create.return_value = created

        result = self.use_case.execute(data)

        self.mock_repo.create.assert_called_once_with(data)
        self.assertEqual(result.key, 'warehouse.dispatch.create')

    def test_new_feature_is_active_by_default(self):
        data = CreateFeatureSchema(module='billing', key='billing.new', label='Nueva', category='features')
        self.mock_repo.create.return_value = _feature(is_active=True)

        result = self.use_case.execute(data)

        self.assertTrue(result.is_active)

    def test_default_category_is_features(self):
        data = CreateFeatureSchema(module='security', key='security.roles.list', label='Listar roles')
        # La categoría por defecto en el schema es 'features'
        self.assertEqual(data.category, 'features')

    def test_custom_category_is_preserved(self):
        data = CreateFeatureSchema(
            module='warehouse',
            key='warehouse.orders.delete',
            label='Eliminar Pedidos',
            category='danger',
        )
        self.mock_repo.create.return_value = _feature(category='danger')

        result = self.use_case.execute(data)

        self.assertEqual(result.category, 'danger')

    def test_repository_exception_propagates(self):
        data = CreateFeatureSchema(module='x', key='x.duplicate', label='Dup')
        self.mock_repo.create.side_effect = ValueError('key ya existe')

        with self.assertRaises(ValueError):
            self.use_case.execute(data)

    def test_returned_feature_has_uuid(self):
        data = CreateFeatureSchema(module='security', key='sec.list', label='Listar')
        feature_with_id = _feature(id=uuid.uuid4())
        self.mock_repo.create.return_value = feature_with_id

        result = self.use_case.execute(data)

        self.assertIsInstance(result.id, uuid.UUID)

    def test_key_is_forwarded_unchanged(self):
        data = CreateFeatureSchema(module='billing', key='billing.invoice.approve', label='Aprobar')
        self.mock_repo.create.return_value = _feature(key='billing.invoice.approve')

        self.use_case.execute(data)

        called_schema = self.mock_repo.create.call_args[0][0]
        self.assertEqual(called_schema.key, 'billing.invoice.approve')


# ── UpdateFeatureUseCase ───────────────────────────────────────────────────────

class TestUpdateFeatureUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = UpdateFeatureUseCase(self.mock_repo)

    def test_updates_label(self):
        data = UpdateFeatureSchema(label='Nuevo label')
        updated = _feature(id=FEATURE_ID, label='Nuevo label')
        self.mock_repo.update.return_value = updated

        result = self.use_case.execute(FEATURE_ID, data)

        self.mock_repo.update.assert_called_once_with(FEATURE_ID, data)
        self.assertEqual(result.label, 'Nuevo label')

    def test_updates_category(self):
        data = UpdateFeatureSchema(category='reporting')
        self.mock_repo.update.return_value = _feature(category='reporting')

        result = self.use_case.execute(FEATURE_ID, data)

        self.assertEqual(result.category, 'reporting')

    def test_deactivates_feature(self):
        data = UpdateFeatureSchema(is_active=False)
        self.mock_repo.update.return_value = _feature(is_active=False)

        result = self.use_case.execute(FEATURE_ID, data)

        self.assertFalse(result.is_active)

    def test_reactivates_feature(self):
        data = UpdateFeatureSchema(is_active=True)
        self.mock_repo.update.return_value = _feature(is_active=True)

        result = self.use_case.execute(FEATURE_ID, data)

        self.assertTrue(result.is_active)

    def test_returns_none_when_feature_does_not_exist(self):
        self.mock_repo.update.return_value = None

        result = self.use_case.execute(uuid.uuid4(), UpdateFeatureSchema())

        self.assertIsNone(result)

    def test_partial_update_sends_schema_to_repository(self):
        data = UpdateFeatureSchema(label='Solo label')
        self.mock_repo.update.return_value = _feature()

        self.use_case.execute(FEATURE_ID, data)

        called_schema = self.mock_repo.update.call_args[0][1]
        self.assertEqual(called_schema.label, 'Solo label')
        self.assertIsNone(called_schema.category)
        self.assertIsNone(called_schema.is_active)

    def test_passes_feature_id_to_repository(self):
        feature_id = uuid.uuid4()
        data = UpdateFeatureSchema(label='X')
        self.mock_repo.update.return_value = _feature()

        self.use_case.execute(feature_id, data)

        self.mock_repo.update.assert_called_once_with(feature_id, data)

    def test_update_without_changes_passes_empty_schema(self):
        data = UpdateFeatureSchema()
        self.mock_repo.update.return_value = _feature()

        self.use_case.execute(FEATURE_ID, data)

        called_schema = self.mock_repo.update.call_args[0][1]
        self.assertIsNone(called_schema.label)
        self.assertIsNone(called_schema.category)
        self.assertIsNone(called_schema.is_active)
