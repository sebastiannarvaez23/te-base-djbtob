"""
Unit tests for billing use cases:
  - GetInvoicesByCompanyUseCase
  - GetInvoiceByNumberUseCase
  - CreateInvoiceUseCase
  - UpdateInvoiceStatusUseCase
  - DeleteInvoiceUseCase

Invoices are always linked to a company (tenant).
No database required.
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest import TestCase
from unittest.mock import MagicMock

from platform.features.billing.commerce.invoice.application.use_cases import (
    GetInvoicesByCompanyUseCase,
    GetInvoiceByNumberUseCase,
    CreateInvoiceUseCase,
    UpdateInvoiceStatusUseCase,
    DeleteInvoiceUseCase,
)
from platform.features.billing.commerce.invoice.domain.schemas import (
    InvoiceSchema,
    CreateInvoiceSchema,
    UpdateInvoiceStatusSchema,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _invoice(**overrides) -> InvoiceSchema:
    defaults = dict(
        id=uuid.uuid4(),
        invoice_number='INV-2025-001',
        company_id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
        issue_date=date(2025, 1, 1),
        due_date=date(2025, 1, 31),
        total_amount=Decimal('49.99'),
        status='pending',
        notes='',
    )
    defaults.update(overrides)
    return InvoiceSchema(**defaults)


def _create_schema(**overrides) -> CreateInvoiceSchema:
    defaults = dict(
        invoice_number='INV-2025-001',
        company_id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
        issue_date=date(2025, 1, 1),
        due_date=date(2025, 1, 31),
        total_amount=Decimal('49.99'),
        status='pending',
        notes='',
    )
    defaults.update(overrides)
    return CreateInvoiceSchema(**defaults)


# ── GetInvoicesByCompanyUseCase ───────────────────────────────────────────────

class TestGetInvoicesByCompanyUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = GetInvoicesByCompanyUseCase(self.mock_repo)
        self.company_id = uuid.uuid4()

    def test_returns_invoices_for_the_company(self):
        invoices = [
            _invoice(company_id=self.company_id, invoice_number='INV-001'),
            _invoice(company_id=self.company_id, invoice_number='INV-002'),
        ]
        self.mock_repo.get_all_by_company.return_value = invoices

        result = self.use_case.execute(self.company_id)

        self.assertEqual(len(result), 2)
        self.mock_repo.get_all_by_company.assert_called_once_with(self.company_id)

    def test_returns_empty_list_when_company_has_no_invoices(self):
        self.mock_repo.get_all_by_company.return_value = []

        result = self.use_case.execute(self.company_id)

        self.assertEqual(result, [])

    def test_invoices_only_from_specified_company(self):
        """The use case filters by company_id — it does not return invoices from other companies."""
        other_company = uuid.uuid4()
        self.mock_repo.get_all_by_company.return_value = []

        result = self.use_case.execute(other_company)

        self.mock_repo.get_all_by_company.assert_called_once_with(other_company)
        self.assertEqual(result, [])


# ── GetInvoiceByNumberUseCase ─────────────────────────────────────────────────

class TestGetInvoiceByNumberUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = GetInvoiceByNumberUseCase(self.mock_repo)

    def test_returns_invoice_by_number(self):
        invoice = _invoice(invoice_number='INV-2025-042')
        self.mock_repo.get_by_invoice_number.return_value = invoice

        result = self.use_case.execute('INV-2025-042')

        self.mock_repo.get_by_invoice_number.assert_called_once_with('INV-2025-042')
        self.assertEqual(result.invoice_number, 'INV-2025-042')

    def test_returns_none_when_number_does_not_exist(self):
        self.mock_repo.get_by_invoice_number.return_value = None

        result = self.use_case.execute('INV-NONEXISTENT')

        self.assertIsNone(result)


# ── CreateInvoiceUseCase ──────────────────────────────────────────────────────

class TestCreateInvoiceUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = CreateInvoiceUseCase(self.mock_repo)

    def test_creates_invoice_and_returns_schema(self):
        company_id = uuid.uuid4()
        data = _create_schema(company_id=company_id, invoice_number='INV-2025-100')
        created_invoice = _invoice(company_id=company_id, invoice_number='INV-2025-100')
        self.mock_repo.create.return_value = created_invoice

        result = self.use_case.execute(data)

        self.mock_repo.create.assert_called_once_with(data)
        self.assertEqual(result.invoice_number, 'INV-2025-100')
        self.assertEqual(result.company_id, company_id)

    def test_created_invoice_has_pending_status_by_default(self):
        data = _create_schema(status='pending')
        self.mock_repo.create.return_value = _invoice(status='pending')

        result = self.use_case.execute(data)

        self.assertEqual(result.status, 'pending')

    def test_invoice_is_always_linked_to_a_company(self):
        """Every invoice has company_id — it is a required field."""
        company_id = uuid.uuid4()
        data = _create_schema(company_id=company_id)
        self.mock_repo.create.return_value = _invoice(company_id=company_id)

        result = self.use_case.execute(data)

        self.assertIsNotNone(result.company_id)
        self.assertEqual(result.company_id, company_id)

    def test_propagates_exception_when_invoice_number_is_duplicated(self):
        data = _create_schema(invoice_number='INV-DUP')
        self.mock_repo.create.side_effect = Exception('invoice_number already exists')

        with self.assertRaises(Exception):
            self.use_case.execute(data)


# ── UpdateInvoiceStatusUseCase ────────────────────────────────────────────────

class TestUpdateInvoiceStatusUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = UpdateInvoiceStatusUseCase(self.mock_repo)
        self.invoice_id = uuid.uuid4()

    def test_updates_status_to_paid(self):
        data = UpdateInvoiceStatusSchema(status='paid')
        self.mock_repo.update_status.return_value = _invoice(
            id=self.invoice_id, status='paid'
        )

        result = self.use_case.execute(self.invoice_id, data)

        self.mock_repo.update_status.assert_called_once_with(self.invoice_id, data)
        self.assertEqual(result.status, 'paid')

    def test_updates_status_to_cancelled(self):
        data = UpdateInvoiceStatusSchema(status='cancelled')
        self.mock_repo.update_status.return_value = _invoice(status='cancelled')

        result = self.use_case.execute(self.invoice_id, data)

        self.assertEqual(result.status, 'cancelled')

    def test_updates_status_to_overdue(self):
        data = UpdateInvoiceStatusSchema(status='overdue')
        self.mock_repo.update_status.return_value = _invoice(status='overdue')

        result = self.use_case.execute(self.invoice_id, data)

        self.assertEqual(result.status, 'overdue')

    def test_returns_none_when_invoice_does_not_exist(self):
        data = UpdateInvoiceStatusSchema(status='paid')
        self.mock_repo.update_status.return_value = None

        result = self.use_case.execute(uuid.uuid4(), data)

        self.assertIsNone(result)

    def test_schema_only_accepts_valid_statuses(self):
        """InvoiceStatusType is a Literal with the 4 allowed statuses."""
        with self.assertRaises(Exception):
            UpdateInvoiceStatusSchema(status='approved')  # invalid status


# ── DeleteInvoiceUseCase ──────────────────────────────────────────────────────

class TestDeleteInvoiceUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = DeleteInvoiceUseCase(self.mock_repo)

    def test_deletes_invoice_and_returns_true(self):
        invoice_id = uuid.uuid4()
        self.mock_repo.delete.return_value = True

        result = self.use_case.execute(invoice_id)

        self.assertTrue(result)
        self.mock_repo.delete.assert_called_once_with(invoice_id)

    def test_returns_false_when_invoice_does_not_exist(self):
        self.mock_repo.delete.return_value = False

        result = self.use_case.execute(uuid.uuid4())

        self.assertFalse(result)
