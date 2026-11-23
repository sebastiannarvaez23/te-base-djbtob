"""
Multitenant isolation tests at the use case and schema level.

Verifies that the business rules guaranteeing tenant isolation are enforced:
each company has its own schema, a unique NIT, and all data (invoices,
payment methods, users) is always scoped to a specific company.

No database required.
"""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock, call, patch

from platform.features.company.tenant.company.application.use_cases import (
    GetCompanyByNitUseCase,
    CreateCompanyUseCase,
)
from platform.features.company.tenant.company.domain.schemas import (
    CompanySchema,
    CreateCompanySchema,
)
from platform.features.billing.commerce.payment_method.application.use_cases import (
    GetPaymentMethodsByCompanyUseCase,
)
from platform.features.billing.commerce.invoice.application.use_cases import (
    GetInvoicesByCompanyUseCase,
)
from client.features.security.identity.identity.application.use_cases import (
    GetUserPreferencesUseCase,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _company(nit='900000001', schema='tenant_001', **overrides) -> CompanySchema:
    return CompanySchema(
        id=uuid.uuid4(),
        schema_name=schema,
        nit=nit,
        name=f'Company {nit}',
        address='123 Main St',
        geo_city_id=uuid.uuid4(),
        country='US',
        state='California',
        city='San Francisco',
        **overrides,
    )


# ── NIT Isolation ─────────────────────────────────────────────────────────────

class TestNITIsolation(TestCase):
    """
    The NIT is the lookup key that differentiates each tenant.
    The system must not confuse data from different companies.
    """

    def test_two_companies_with_different_nits_are_not_confused(self):
        mock_repo = MagicMock()
        use_case = GetCompanyByNitUseCase(mock_repo)

        company_a = _company(nit='100000001', schema='tenant_a')
        company_b = _company(nit='200000002', schema='tenant_b')
        mock_repo.get_by_nit.side_effect = {
            '100000001': company_a,
            '200000002': company_b,
        }.get

        result_a = use_case.execute('100000001')
        result_b = use_case.execute('200000002')

        self.assertNotEqual(result_a.id, result_b.id)
        self.assertNotEqual(result_a.schema_name, result_b.schema_name)
        self.assertNotEqual(result_a.nit, result_b.nit)

    def test_wrong_nit_returns_none_not_data_from_another_tenant(self):
        mock_repo = MagicMock()
        mock_repo.get_by_nit.return_value = None
        use_case = GetCompanyByNitUseCase(mock_repo)

        result = use_case.execute('999999999')

        self.assertIsNone(result)

    def test_each_query_uses_exact_nit_without_cross_contamination(self):
        mock_repo = MagicMock()
        use_case = GetCompanyByNitUseCase(mock_repo)
        mock_repo.get_by_nit.return_value = _company()

        use_case.execute('111111111')
        use_case.execute('222222222')
        use_case.execute('333333333')

        mock_repo.get_by_nit.assert_has_calls([
            call('111111111'),
            call('222222222'),
            call('333333333'),
        ])


# ── PostgreSQL Schema Isolation ───────────────────────────────────────────────

class TestSchemaIsolation(TestCase):
    """
    Each company has a unique schema_name in PostgreSQL.
    This schema physically separates data for each tenant.
    """

    def test_schema_name_is_unique_per_company(self):
        mock_repo = MagicMock()
        use_case = CreateCompanyUseCase(mock_repo)

        created_schemas = set()
        with patch(
            'platform.features.company.tenant.company.application.geo_city.assert_active_geo_city',
        ):
            for i in range(3):
                data = CreateCompanySchema(
                    schema_name=f'tenant_{i:03d}',
                    nit=f'90000000{i}',
                    name=f'Company {i}',
                    address='123 Main St',
                    geo_city_id=uuid.uuid4(),
                    subscription_id=uuid.uuid4(),
                )
                mock_repo.create.return_value = _company(
                    nit=data.nit, schema=data.schema_name
                )
                result = use_case.execute(data)
                created_schemas.add(result.schema_name)

        self.assertEqual(len(created_schemas), 3)

    def test_subscription_id_required_when_creating_tenant(self):
        """
        A company without a plan cannot be created.
        subscription_id is mandatory in CreateCompanySchema.
        """
        with self.assertRaises(Exception):
            CreateCompanySchema(
                schema_name='tenant_no_plan',
                nit='000000001',
                name='No Plan Corp',
                address='X',
                geo_city_id=uuid.uuid4(),
                # subscription_id omitted — must raise
            )

    def test_same_data_with_different_subscription_creates_distinct_tenants(self):
        """Two companies can share the same data except for NIT and subscription_id."""
        sub_1 = uuid.uuid4()
        sub_2 = uuid.uuid4()

        data_1 = CreateCompanySchema(
            schema_name='tenant_001', nit='111', name='X', address='X',
            geo_city_id=uuid.uuid4(), subscription_id=sub_1,
        )
        data_2 = CreateCompanySchema(
            schema_name='tenant_002', nit='222', name='X', address='X',
            geo_city_id=uuid.uuid4(), subscription_id=sub_2,
        )

        self.assertNotEqual(data_1.schema_name, data_2.schema_name)
        self.assertNotEqual(data_1.subscription_id, data_2.subscription_id)


# ── Payment Method Isolation per Company ──────────────────────────────────────

class TestPaymentMethodIsolation(TestCase):
    """
    Payment methods belong to a specific company.
    The use case only returns methods for the queried company.
    """

    def test_methods_from_one_company_are_not_visible_to_another(self):
        from core.query.core import PaginatedQuery, PaginatedResult

        mock_repo = MagicMock()
        use_case = GetPaymentMethodsByCompanyUseCase(mock_repo)
        query = PaginatedQuery(page=0, page_size=0, filters={}, unpaginated=True)

        company_a = uuid.uuid4()
        company_b = uuid.uuid4()

        methods_a = [MagicMock(company_id=company_a) for _ in range(2)]
        mock_repo.get_all_by_company.side_effect = lambda cid, q: (
            PaginatedResult(items=methods_a, total=2, page=0, page_size=0, total_pages=1)
            if cid == company_a
            else PaginatedResult(items=[], total=0, page=0, page_size=0, total_pages=1)
        )

        result_a = use_case.execute(company_a, query)
        result_b = use_case.execute(company_b, query)

        self.assertEqual(len(result_a.items), 2)
        self.assertEqual(len(result_b.items), 0)

    def test_repository_filters_by_company_id_not_globally(self):
        from core.query.core import PaginatedQuery, PaginatedResult

        mock_repo = MagicMock()
        use_case = GetPaymentMethodsByCompanyUseCase(mock_repo)
        company_id = uuid.uuid4()
        query = PaginatedQuery(page=0, page_size=0, filters={}, unpaginated=True)
        mock_repo.get_all_by_company.return_value = PaginatedResult(
            items=[], total=0, page=0, page_size=0, total_pages=1,
        )

        use_case.execute(company_id, query)

        mock_repo.get_all_by_company.assert_called_once_with(company_id, query)


# ── Invoice Isolation per Company ─────────────────────────────────────────────

class TestInvoiceIsolation(TestCase):
    """
    Invoices are linked to a specific company.
    A company must never see invoices belonging to another company.
    """

    def test_invoices_from_company_a_do_not_appear_for_company_b(self):
        mock_repo = MagicMock()
        use_case = GetInvoicesByCompanyUseCase(mock_repo)

        company_a = uuid.uuid4()
        company_b = uuid.uuid4()

        invoices_a = [MagicMock(company_id=company_a) for _ in range(3)]
        mock_repo.get_all_by_company.side_effect = lambda cid: (
            invoices_a if cid == company_a else []
        )

        result_a = use_case.execute(company_a)
        result_b = use_case.execute(company_b)

        self.assertEqual(len(result_a), 3)
        self.assertEqual(len(result_b), 0)

    def test_fetching_invoices_always_requires_company_id(self):
        mock_repo = MagicMock()
        use_case = GetInvoicesByCompanyUseCase(mock_repo)
        company_id = uuid.uuid4()
        mock_repo.get_all_by_company.return_value = []

        use_case.execute(company_id)

        mock_repo.get_all_by_company.assert_called_once_with(company_id)


# ── User Preference Isolation ─────────────────────────────────────────────────

class TestUserPreferenceIsolation(TestCase):
    """
    Preferences are scoped to a user_id.
    Two users never share preferences.
    """

    def test_preferences_from_user_a_do_not_affect_user_b(self):
        mock_repo = MagicMock()
        use_case = GetUserPreferencesUseCase(mock_repo)

        user_a = uuid.uuid4()
        user_b = uuid.uuid4()

        prefs_a = MagicMock(user_id=user_a, language='en')
        prefs_b = MagicMock(user_id=user_b, language='es')
        mock_repo.get_or_create.side_effect = lambda uid: (
            prefs_a if uid == user_a else prefs_b
        )

        result_a = use_case.execute(user_a)
        result_b = use_case.execute(user_b)

        self.assertEqual(result_a.language, 'en')
        self.assertEqual(result_b.language, 'es')
        self.assertNotEqual(result_a.user_id, result_b.user_id)

    def test_each_call_uses_the_correct_user_id(self):
        mock_repo = MagicMock()
        use_case = GetUserPreferencesUseCase(mock_repo)
        user_id = uuid.uuid4()
        mock_repo.get_or_create.return_value = MagicMock()

        use_case.execute(user_id)

        mock_repo.get_or_create.assert_called_once_with(user_id)
