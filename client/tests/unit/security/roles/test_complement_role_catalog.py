"""Complementos fuera de permisos de rol, salvo los que la empresa ya contrató."""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch

import pytest

from client.features.security.access.roles.domain.schemas import UpdateRoleFeaturesSchema
from client.features.security.access.roles.infrastructure.repositories import DjangoRoleRepository
from core.errors.codes import AppErrorCode
from core.errors.exceptions import ValidationAppException
from core.query.core import PaginatedQuery

pytestmark = pytest.mark.unit

_REPO = 'client.features.security.access.roles.infrastructure.repositories'


def _query() -> PaginatedQuery:
    return PaginatedQuery(page=0, page_size=0, filters={}, unpaginated=True)


def _row(key: str, offering: str = 'plan'):
    row = MagicMock()
    row.key = key
    row.label = key
    row.category = 'access'
    row.offering = offering
    row.module.code = key.split('.')[0]
    return row


class TestComplementRoleCatalog(TestCase):

    @patch(f'{_REPO}.Functionality')
    def test_platform_catalog_excludes_complements(self, MockFunctionality):
        plan = _row('orders.view')
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.exclude.return_value = [plan]
        MockFunctionality.objects.select_related.return_value.order_by.return_value = qs

        result = DjangoRoleRepository().get_all_features(_query())

        qs.exclude.assert_called_once_with(offering='complement')
        self.assertEqual([item.key for item in result.items], ['orders.view'])

    @patch(f'{_REPO}.Functionality')
    def test_company_catalog_keeps_licensed_complements(self, MockFunctionality):
        with patch(
            'platform.features.billing.complement.entitlement.infrastructure.active.active_complement_access',
            return_value=({'connectors.sap'}, {'connectors'}),
        ):
            licensed = _row('connectors.sap', offering='complement')
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.__iter__.return_value = iter([licensed])
            MockFunctionality.objects.select_related.return_value.order_by.return_value = qs

            result = DjangoRoleRepository().get_all_features(_query(), uuid.uuid4())

        self.assertEqual([item.key for item in result.items], ['connectors.sap'])
        qs.exclude.assert_not_called()


class TestComplementRoleAssignment(TestCase):

    def test_company_role_rejects_unlicensed_complement(self):
        repo = DjangoRoleRepository()
        company_id = uuid.uuid4()
        rol = MagicMock()
        rol.company_id = company_id
        complement = _row('connectors.sap', offering='complement')

        with patch(f'{_REPO}.transaction.atomic') as mock_atomic, \
                patch(f'{_REPO}.Rol') as MockRol, \
                patch(f'{_REPO}.Functionality') as MockFunctionality, \
                patch(
                    'platform.features.billing.complement.entitlement.infrastructure.active.active_complement_access',
                    return_value=(set(), set()),
                ):
            mock_atomic.return_value.__exit__.return_value = False
            MockRol.DoesNotExist = type('DoesNotExist', (Exception,), {})
            MockRol.objects.get.return_value = rol
            MockRol.objects.select_for_update.return_value.get.return_value = rol
            MockFunctionality.objects.filter.return_value = [complement]

            with self.assertRaises(ValidationAppException) as ctx:
                repo.update_features(
                    uuid.uuid4(),
                    company_id,
                    UpdateRoleFeaturesSchema(feature_keys=['connectors.sap']),
                )

        self.assertEqual(ctx.exception.code, AppErrorCode.CMP_NOT_AVAILABLE)

    def test_shared_role_rejects_complement_keys(self):
        repo = DjangoRoleRepository()
        rol = MagicMock()
        rol.company_id = None
        complement = _row('connectors.sap', offering='complement')

        with patch(f'{_REPO}.transaction.atomic') as mock_atomic, \
                patch(f'{_REPO}.Rol') as MockRol, \
                patch(f'{_REPO}.Functionality') as MockFunctionality:
            mock_atomic.return_value.__exit__.return_value = False
            MockRol.DoesNotExist = type('DoesNotExist', (Exception,), {})
            MockRol.objects.get.return_value = rol
            MockRol.objects.select_for_update.return_value.get.return_value = rol
            MockFunctionality.objects.filter.return_value = [complement]

            with self.assertRaises(ValidationAppException) as ctx:
                repo.update_generic_role_features(
                    uuid.uuid4(),
                    UpdateRoleFeaturesSchema(feature_keys=['connectors.sap']),
                )

        self.assertEqual(ctx.exception.code, AppErrorCode.CMP_NOT_AVAILABLE)


class TestRoleListGrantQueries(TestCase):

    @patch(f'{_REPO}.CompanyRolAccess')
    @patch(f'{_REPO}.RolModule')
    @patch(f'{_REPO}.RolFeature')
    @patch(f'{_REPO}.Rol')
    def test_list_loads_grants_for_the_page_in_one_query(
        self, MockRol, MockRolFeature, MockRolModule, MockAccess,
    ):
        company_id = uuid.uuid4()
        admin_id = uuid.uuid4()
        operator_id = uuid.uuid4()
        admin = MagicMock()
        admin.id = admin_id
        admin.name = 'Administrator'
        admin.company_id = None
        admin.description = ''
        admin.is_active = True
        operator = MagicMock()
        operator.id = operator_id
        operator.name = 'Operator'
        operator.company_id = company_id
        operator.description = ''
        operator.is_active = True
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.__iter__.return_value = iter([admin, operator])
        MockRol.objects.filter.return_value.order_by.return_value = qs
        MockRolFeature.objects.filter.return_value.values_list.return_value = [
            (operator_id, 'orders.view'),
        ]
        MockRolModule.objects.filter.return_value.values_list.return_value = [
            (operator_id, 'orders'),
        ]
        MockAccess.objects.filter.return_value = []

        with patch(
            'platform.features.billing.complement.entitlement.infrastructure.active.active_complement_access',
            return_value=({'connectors.sap'}, {'connectors'}),
        ) as complements:
            result = DjangoRoleRepository().get_all(company_id, _query())

        self.assertEqual(MockRolFeature.objects.filter.call_count, 1)
        self.assertEqual(
            set(MockRolFeature.objects.filter.call_args.kwargs['rol_id__in']),
            {admin_id, operator_id},
        )
        self.assertEqual(MockRolModule.objects.filter.call_count, 1)
        self.assertEqual(MockAccess.objects.filter.call_count, 1)
        complements.assert_called_once()
        by_name = {item.name: item for item in result.items}
        self.assertIn('connectors.sap', by_name['Administrator'].features)
        self.assertEqual(by_name['Operator'].features, ['orders.view'])
        self.assertNotIn('connectors.sap', by_name['Operator'].features)
