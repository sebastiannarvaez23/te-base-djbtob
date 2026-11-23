"""Unit tests for catalog request bodies (sections / modules)."""
import unittest

from core.validators import ValidationCode
from platform.features.security.access.modules.presentation.bodies import (
    CreateModuleBody,
    UpdateModuleBody,
)
from platform.features.security.access.roles.presentation.bodies import (
    CreateAdminModuleBody,
    UpdateAdminModuleBody,
)
from platform.features.security.access.sections.presentation.bodies import (
    CreateSectionBody,
    UpdateSectionBody,
)


class TestCreateSectionBody(unittest.TestCase):

    def test_accepts_icon(self):
        body = CreateSectionBody({
            'code': 'IA',
            'name': 'IA',
            'icon': 'bx-category',
        })
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertEqual(body.validated_data['icon'], 'bx-category')
        self.assertEqual(body.validated_data['code'], 'IA')

    def test_icon_optional_defaults_empty(self):
        body = CreateSectionBody({'code': 'OPS', 'name': 'Operaciones'})
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertEqual(body.validated_data.get('icon', ''), '')


class TestUpdateSectionBody(unittest.TestCase):

    def test_accepts_code(self):
        body = UpdateSectionBody({
            'code': 'operational',
            'name': 'Operativo',
            'icon': 'bx-factory',
        })
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertEqual(body.validated_data['code'], 'operational')
        self.assertEqual(body.validated_data['name'], 'Operativo')
        self.assertEqual(body.validated_data['icon'], 'bx-factory')

    def test_code_optional_on_partial_update(self):
        body = UpdateSectionBody({'name': 'Operativo'})
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertNotIn('code', body.validated_data)


class TestCreateModuleBody(unittest.TestCase):

    def _payload(self, **overrides):
        data = {
            'code': 'ORDERS',
            'name': 'Pedidos',
            'icon': 'bx-cart',
            'route': '/warehouse/orders',
            'section_id': '11111111-1111-1111-1111-111111111111',
        }
        data.update(overrides)
        return data

    def test_is_sidebar_defaults_true(self):
        body = CreateModuleBody(self._payload())
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertTrue(body.validated_data['is_sidebar'])

    def test_accepts_is_sidebar_false(self):
        body = CreateModuleBody(self._payload(is_sidebar=False))
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertFalse(body.validated_data['is_sidebar'])

    def test_route_required_when_sidebar(self):
        payload = self._payload()
        del payload['route']
        body = CreateModuleBody(payload)
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'route')
        self.assertEqual(errors[0].code, ValidationCode.REQUIRED)

    def test_route_optional_when_not_sidebar(self):
        payload = self._payload(is_sidebar=False)
        del payload['route']
        body = CreateModuleBody(payload)
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertEqual(body.validated_data['route'], '')
        self.assertFalse(body.validated_data['is_sidebar'])

    def test_rejects_unknown_field(self):
        body = CreateModuleBody(self._payload(unknown='x'))
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertIn(ValidationCode.UNKNOWN_FIELD, [e.code for e in errors])

    def test_section_id_must_be_uuid(self):
        body = CreateModuleBody(self._payload(section_id='not-a-uuid'))
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertTrue(any(e.field == 'section_id' for e in errors))


class TestUpdateModuleBody(unittest.TestCase):

    def test_allows_empty_route_when_not_sidebar(self):
        body = UpdateModuleBody({'is_sidebar': False, 'route': ''})
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertEqual(body.validated_data['route'], '')

    def test_route_required_when_enabling_sidebar_with_empty_route(self):
        body = UpdateModuleBody({'is_sidebar': True, 'route': ''})
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].code, ValidationCode.REQUIRED)

    def test_route_required_when_enabling_sidebar_without_route(self):
        body = UpdateModuleBody({'is_sidebar': True})
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'route')
        self.assertEqual(errors[0].code, ValidationCode.REQUIRED)

    def test_rejects_code_as_immutable(self):
        body = UpdateModuleBody({'code': 'ORDERS', 'name': 'Pedidos'})
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertIn(ValidationCode.UNKNOWN_FIELD, [e.code for e in errors])
        self.assertTrue(any(e.field == 'code' for e in errors))


class TestCreateAdminModuleBody(unittest.TestCase):

    def _payload(self, **overrides):
        data = {
            'code': 'IA',
            'name': 'IA',
            'icon': 'bx-chip',
            'route': '/admin/ia',
            'section_id': '11111111-1111-1111-1111-111111111111',
        }
        data.update(overrides)
        return data

    def test_route_optional_when_not_sidebar(self):
        payload = self._payload(is_sidebar=False)
        del payload['route']
        body = CreateAdminModuleBody(payload)
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertEqual(body.validated_data['route'], '')

    def test_route_required_when_sidebar(self):
        payload = self._payload()
        del payload['route']
        body = CreateAdminModuleBody(payload)
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].code, ValidationCode.REQUIRED)


class TestUpdateAdminModuleBody(unittest.TestCase):

    def test_rejects_code_as_immutable(self):
        body = UpdateAdminModuleBody({'code': 'IA', 'name': 'IA'})
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertIn(ValidationCode.UNKNOWN_FIELD, [e.code for e in errors])
        self.assertTrue(any(e.field == 'code' for e in errors))


class TestReorderCatalogBody(unittest.TestCase):

    def test_accepts_ids(self):
        from platform.features.security.access.roles.presentation.bodies import ReorderCatalogBody
        from platform.features.security.access.sections.presentation.bodies import ReorderSectionBody

        ids = [
            '11111111-1111-1111-1111-111111111111',
            '22222222-2222-2222-2222-222222222222',
        ]
        body = ReorderCatalogBody({'ids': ids})
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertEqual(body.validated_data['ids'], ids)

        section_body = ReorderSectionBody({'ids': ids})
        ok, errors = section_body.validate()
        self.assertTrue(ok, errors)

    def test_rejects_empty_ids(self):
        from platform.features.security.access.roles.presentation.bodies import ReorderCatalogBody

        body = ReorderCatalogBody({'ids': []})
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertTrue(errors)
