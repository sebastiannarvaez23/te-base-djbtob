"""
Unit tests for company (tenant) use cases:
  - GetCompanyByNitUseCase
  - CreateCompanyUseCase

The NIT is the primary identifier for each tenant.
No database required.
"""
import uuid
import pytest
from unittest import TestCase
from unittest.mock import MagicMock, patch

from platform.features.company.tenant.company.application.use_cases import (
    GetCompanyByNitUseCase,
    GetCompanyDetailByIdUseCase,
    CreateCompanyUseCase,
    UpdateCompanySettingsUseCase,
)
from platform.features.company.tenant.company.domain.schemas import (
    CompanyDetailSchema,
    CompanySchema,
    CreateCompanySchema,
    UpdateCompanySchema,
)
from core.errors import AppErrorCode, ConflictException

pytestmark = pytest.mark.unit


# ── Helpers ─────────────────────────────────────────────────────────────────

def _company(**overrides) -> CompanySchema:
    defaults = dict(
        id=uuid.uuid4(),
        schema_name='acme_corp',
        nit='900123456',
        name='Acme Corp',
        address='123 Main St',
        geo_city_id=uuid.uuid4(),
        country='US',
        state='California',
        city='San Francisco',
    )
    defaults.update(overrides)
    return CompanySchema(**defaults)


def _detail(**overrides) -> CompanyDetailSchema:
    defaults = dict(
        id=uuid.uuid4(),
        schema_name='acme_corp',
        nit='900123456',
        name='Acme Corp',
        address='123 Main St',
        geo_city_id=uuid.uuid4(),
        country='US',
        state='California',
        city='San Francisco',
        is_registered=True,
    )
    defaults.update(overrides)
    if 'is_registered' not in overrides:
        defaults['is_registered'] = bool((defaults.get('nit') or '').strip())
    return CompanyDetailSchema(**defaults)


def _create_schema(**overrides) -> CreateCompanySchema:
    defaults = dict(
        schema_name='acme_corp',
        nit='900123456',
        name='Acme Corp',
        address='123 Main St',
        geo_city_id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
    )
    defaults.update(overrides)
    return CreateCompanySchema(**defaults)


# ── GetCompanyByNitUseCase ───────────────────────────────────────────────────

class TestGetCompanyByNitUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = GetCompanyByNitUseCase(self.mock_repo)

    def test_returns_company_when_nit_exists(self):
        company = _company(nit='900123456')
        self.mock_repo.get_by_nit.return_value = company

        result = self.use_case.execute('900123456')

        self.assertEqual(result.nit, '900123456')
        self.assertEqual(result.name, 'Acme Corp')

    def test_delegates_search_to_repository_with_exact_nit(self):
        self.mock_repo.get_by_nit.return_value = _company()

        self.use_case.execute('900123456')

        self.mock_repo.get_by_nit.assert_called_once_with('900123456')

    def test_returns_none_when_nit_does_not_exist(self):
        self.mock_repo.get_by_nit.return_value = None

        result = self.use_case.execute('000000000')

        self.assertIsNone(result)

    def test_different_nits_look_up_different_tenants(self):
        """Each NIT identifies a unique tenant in the multitenant system."""
        company_a = _company(nit='111111111', schema_name='tenant_a')
        company_b = _company(nit='222222222', schema_name='tenant_b')

        self.mock_repo.get_by_nit.side_effect = lambda nit: (
            company_a if nit == '111111111' else company_b
        )

        result_a = self.use_case.execute('111111111')
        result_b = self.use_case.execute('222222222')

        self.assertNotEqual(result_a.schema_name, result_b.schema_name)
        self.assertNotEqual(result_a.nit, result_b.nit)


# ── CreateCompanyUseCase ─────────────────────────────────────────────────────

class TestCreateCompanyUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = CreateCompanyUseCase(self.mock_repo)
        self._geo = patch(
            'platform.features.company.tenant.company.application.geo_city.assert_active_geo_city',
        )
        self._geo.start()
        self.addCleanup(self._geo.stop)

    def test_creates_company_and_returns_schema(self):
        data = _create_schema()
        created_company = _company(nit=data.nit, schema_name=data.schema_name)
        self.mock_repo.create.return_value = created_company

        result = self.use_case.execute(data)

        self.mock_repo.create.assert_called_once_with(data)
        self.assertEqual(result.nit, data.nit)
        self.assertEqual(result.schema_name, data.schema_name)

    def test_each_created_company_has_unique_schema_name(self):
        """The schema_name is the PostgreSQL schema identifier for the tenant."""
        data_a = _create_schema(schema_name='tenant_alpha', nit='111111111')
        data_b = _create_schema(schema_name='tenant_beta', nit='222222222')

        self.mock_repo.create.side_effect = [
            _company(schema_name='tenant_alpha', nit='111111111'),
            _company(schema_name='tenant_beta', nit='222222222'),
        ]

        result_a = self.use_case.execute(data_a)
        result_b = self.use_case.execute(data_b)

        self.assertNotEqual(result_a.schema_name, result_b.schema_name)

    def test_creation_requires_subscription_id(self):
        """
        CreateCompanySchema requires subscription_id.
        Every newly created company must be associated with a plan.
        """
        with self.assertRaises(Exception):
            CreateCompanySchema(
                schema_name='tenant_x',
                nit='900000000',
                name='No Plan Corp',
                address='Street 0',
                geo_city_id=uuid.uuid4(),
                # subscription_id missing — must raise
            )

    def test_schema_name_and_nit_are_different_data(self):
        """The schema_name is the technical schema identifier; the NIT is the tax ID."""
        data = _create_schema(schema_name='acme_corp_001', nit='900111222')
        self.mock_repo.create.return_value = _company(
            schema_name='acme_corp_001', nit='900111222'
        )

        result = self.use_case.execute(data)

        self.assertEqual(result.schema_name, 'acme_corp_001')
        self.assertEqual(result.nit, '900111222')
        self.assertNotEqual(result.schema_name, result.nit)

    def test_propagates_exception_when_nit_already_exists(self):
        data = _create_schema(nit='900123456')
        self.mock_repo.create.side_effect = Exception('NIT already registered')

        with self.assertRaises(Exception, msg='NIT already registered'):
            self.use_case.execute(data)


class TestGetCompanyDetailByIdUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = GetCompanyDetailByIdUseCase(self.mock_repo)

    def test_returns_detail_for_unregistered_company(self):
        company_id = uuid.uuid4()
        self.mock_repo.get_detail_by_id.return_value = _detail(
            id=company_id,
            nit='',
            is_registered=False,
        )

        result = self.use_case.execute(company_id)

        self.assertEqual(result.id, company_id)
        self.assertEqual(result.nit, '')
        self.assertFalse(result.is_registered)
        self.mock_repo.get_detail_by_id.assert_called_once_with(company_id)


class TestUpdateCompanySettingsUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = UpdateCompanySettingsUseCase(self.mock_repo)
        self.company_id = uuid.uuid4()

    def test_sets_nit_when_company_has_none(self):
        self.mock_repo.get_by_id.return_value = _company(
            id=self.company_id,
            nit='',
        )
        self.mock_repo.get_by_nit.return_value = None
        self.mock_repo.update_settings.return_value = _detail(
            id=self.company_id,
            nit='900999888',
            is_registered=True,
        )

        result = self.use_case.execute(
            self.company_id,
            UpdateCompanySchema(name='Acme Corp', nit='900999888'),
        )

        self.assertEqual(result.nit, '900999888')
        self.assertTrue(result.is_registered)
        payload = self.mock_repo.update_settings.call_args[0][1]
        self.assertEqual(payload.nit, '900999888')

    def test_ignores_nit_change_when_already_registered(self):
        self.mock_repo.get_by_id.return_value = _company(
            id=self.company_id,
            nit='900123456',
        )
        self.mock_repo.update_settings.return_value = _detail(id=self.company_id)

        self.use_case.execute(
            self.company_id,
            UpdateCompanySchema(name='New Name', nit='111222333'),
        )

        payload = self.mock_repo.update_settings.call_args[0][1]
        self.assertIsNone(payload.nit)
        self.mock_repo.get_by_nit.assert_not_called()

    def test_rejects_duplicate_nit(self):
        self.mock_repo.get_by_id.return_value = _company(
            id=self.company_id,
            nit='',
        )
        other_id = uuid.uuid4()
        self.mock_repo.get_by_nit.return_value = _company(id=other_id, nit='900123456')

        with self.assertRaises(ConflictException) as ctx:
            self.use_case.execute(
                self.company_id,
                UpdateCompanySchema(nit='900123456'),
            )
        self.assertEqual(ctx.exception.code, AppErrorCode.COMPANY_DUPLICATE_NIT)
