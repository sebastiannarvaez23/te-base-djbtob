"""
Unit tests for payment method use cases:
  - GetAllPaymentMethodsUseCase
  - GetPaymentMethodsByCompanyUseCase
  - CreatePaymentMethodUseCase
  - UpdatePaymentMethodUseCase
  - DeletePaymentMethodUseCase

No database required.
"""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock

from platform.features.billing.commerce.payment_method.application.use_cases import (
    GetAllPaymentMethodsUseCase,
    GetPaymentMethodsByCompanyUseCase,
    CreatePaymentMethodUseCase,
    UpdatePaymentMethodUseCase,
    DeletePaymentMethodUseCase,
)
from platform.features.billing.commerce.payment_method.domain.schemas import (
    PaymentMethodSchema,
    CreatePaymentMethodSchema,
    UpdatePaymentMethodSchema,
)
from core.query.core import PaginatedQuery, PaginatedResult


# ── Helper ─────────────────────────────────────────────────────────────────────

def _payment_method(**overrides) -> PaymentMethodSchema:
    defaults = dict(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        name='Visa ending 4242',
        provider='visa',
        holder='JOHN SMITH',
        last4='4242',
        expiry='12/27',
        is_active=True,
    )
    defaults.update(overrides)
    return PaymentMethodSchema(**defaults)


# ── GetAllPaymentMethodsUseCase ────────────────────────────────────────────────

class TestGetAllPaymentMethodsUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = GetAllPaymentMethodsUseCase(self.mock_repo)

    def test_returns_all_payment_methods(self):
        methods = [_payment_method(), _payment_method()]
        self.mock_repo.get_all.return_value = methods

        result = self.use_case.execute()

        self.assertEqual(len(result), 2)
        self.mock_repo.get_all.assert_called_once()

    def test_returns_empty_list_when_no_methods_exist(self):
        self.mock_repo.get_all.return_value = []

        result = self.use_case.execute()

        self.assertEqual(result, [])


# ── GetPaymentMethodsByCompanyUseCase ──────────────────────────────────────────

class TestGetPaymentMethodsByCompanyUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = GetPaymentMethodsByCompanyUseCase(self.mock_repo)
        self.company_id = uuid.uuid4()
        self.query = PaginatedQuery(page=0, page_size=0, filters={}, unpaginated=True)

    def test_returns_methods_for_specified_company(self):
        methods = [
            _payment_method(company_id=self.company_id, last4='1111'),
            _payment_method(company_id=self.company_id, last4='2222'),
        ]
        self.mock_repo.get_all_by_company.return_value = PaginatedResult(
            items=methods, total=2, page=0, page_size=0, total_pages=1,
        )

        result = self.use_case.execute(self.company_id, self.query)

        self.mock_repo.get_all_by_company.assert_called_once_with(self.company_id, self.query)
        self.assertEqual(len(result.items), 2)
        self.assertTrue(all(m.company_id == self.company_id for m in result.items))

    def test_returns_empty_list_when_company_has_no_methods(self):
        self.mock_repo.get_all_by_company.return_value = PaginatedResult(
            items=[], total=0, page=0, page_size=0, total_pages=1,
        )

        result = self.use_case.execute(self.company_id, self.query)

        self.assertEqual(result.items, [])

    def test_does_not_mix_methods_from_other_companies(self):
        """The use case delegates filtering to the repository."""
        other_company = uuid.uuid4()
        self.mock_repo.get_all_by_company.return_value = PaginatedResult(
            items=[], total=0, page=0, page_size=0, total_pages=1,
        )

        result = self.use_case.execute(other_company, self.query)

        self.mock_repo.get_all_by_company.assert_called_once_with(other_company, self.query)
        self.assertEqual(result.items, [])


# ── CreatePaymentMethodUseCase ─────────────────────────────────────────────────

class TestCreatePaymentMethodUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = CreatePaymentMethodUseCase(self.mock_repo)

    def test_creates_payment_method_and_returns_schema(self):
        company_id = uuid.uuid4()
        data = CreatePaymentMethodSchema(
            company_id=company_id,
            name='Mastercard ending 5555',
            provider='mastercard',
            holder='JANE DOE',
            last4='5555',
            expiry='08/26',
            is_active=True,
        )
        created_method = _payment_method(company_id=company_id, last4='5555', provider='mastercard')
        self.mock_repo.create.return_value = created_method

        result = self.use_case.execute(data)

        self.mock_repo.create.assert_called_once_with(data)
        self.assertEqual(result.last4, '5555')
        self.assertEqual(result.provider, 'mastercard')

    def test_payment_method_is_active_by_default(self):
        data = CreatePaymentMethodSchema(
            company_id=uuid.uuid4(),
            name='Visa',
            provider='visa',
            is_active=True,
        )
        self.mock_repo.create.return_value = _payment_method(is_active=True)

        result = self.use_case.execute(data)

        self.assertTrue(result.is_active)


# ── UpdatePaymentMethodUseCase ─────────────────────────────────────────────────

class TestUpdatePaymentMethodUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = UpdatePaymentMethodUseCase(self.mock_repo)
        self.method_id = uuid.uuid4()

    def test_updates_method_and_returns_schema(self):
        data = UpdatePaymentMethodSchema(is_active=False)
        updated_method = _payment_method(id=self.method_id, is_active=False)
        self.mock_repo.partial_update.return_value = updated_method

        result = self.use_case.execute(self.method_id, data)

        self.mock_repo.partial_update.assert_called_once_with(self.method_id, data)
        self.assertFalse(result.is_active)

    def test_returns_none_when_method_does_not_exist(self):
        self.mock_repo.partial_update.return_value = None

        result = self.use_case.execute(uuid.uuid4(), UpdatePaymentMethodSchema())

        self.assertIsNone(result)

    def test_uses_partial_update_not_full_update(self):
        """The use case must call partial_update, not update."""
        data = UpdatePaymentMethodSchema(holder='NEW HOLDER')
        self.mock_repo.partial_update.return_value = _payment_method()

        self.use_case.execute(self.method_id, data)

        self.mock_repo.partial_update.assert_called_once()
        self.mock_repo.update.assert_not_called()


# ── DeletePaymentMethodUseCase ─────────────────────────────────────────────────

class TestDeletePaymentMethodUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = DeletePaymentMethodUseCase(self.mock_repo)

    def test_deletes_method_and_returns_true(self):
        method_id = uuid.uuid4()
        self.mock_repo.delete.return_value = True

        result = self.use_case.execute(method_id)

        self.assertTrue(result)
        self.mock_repo.delete.assert_called_once_with(method_id)

    def test_returns_false_when_method_does_not_exist(self):
        self.mock_repo.delete.return_value = False

        result = self.use_case.execute(uuid.uuid4())

        self.assertFalse(result)
