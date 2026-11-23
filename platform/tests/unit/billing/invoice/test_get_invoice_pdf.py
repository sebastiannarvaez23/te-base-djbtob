"""Unit tests for GetInvoicePdfUseCase DI and stored vs render paths."""

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock

import pytest

from core.errors import AppErrorCode, NotFoundException
from platform.features.billing.commerce.invoice.application.get_invoice_pdf import (
    GetInvoicePdfUseCase,
)
from platform.features.billing.commerce.invoice.domain.schemas import InvoiceSchema

pytestmark = pytest.mark.unit


def _invoice(**overrides) -> InvoiceSchema:
    defaults = dict(
        id=uuid.uuid4(),
        invoice_number='INV-2026-PDF',
        company_id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
        issue_date=date(2026, 7, 11),
        due_date=date(2026, 8, 11),
        total_amount=Decimal('10.00'),
        currency='USD',
        status='paid',
        notes='',
        metadata={},
        pdf_bucket='',
        pdf_object_key='',
    )
    defaults.update(overrides)
    return InvoiceSchema(**defaults)


class TestGetInvoicePdfUseCase(TestCase):

    def test_requires_template_loader(self):
        with self.assertRaises(TypeError):
            GetInvoicePdfUseCase(
                invoice_repo=MagicMock(),
                storage=MagicMock(),
                directory=MagicMock(),
            )

    def test_stored_copy_skips_render(self):
        invoice = _invoice(pdf_bucket='base', pdf_object_key='invoices/a.pdf')
        invoice_repo = MagicMock()
        invoice_repo.get_by_id.return_value = invoice
        storage = MagicMock()
        storage.download_file.return_value = b'%PDF-stored'
        template_loader = MagicMock()
        render_resolver = MagicMock()
        path_resolver = MagicMock()

        result = GetInvoicePdfUseCase(
            invoice_repo=invoice_repo,
            storage=storage,
            directory=MagicMock(),
            template_loader=template_loader,
            render_resolver=render_resolver,
            path_resolver=path_resolver,
        ).execute(invoice.id)

        self.assertEqual(result.blob, b'%PDF-stored')
        self.assertEqual(result.filename, 'INV-2026-PDF.pdf')
        template_loader.load.assert_not_called()
        render_resolver.resolve.assert_not_called()

    def test_missing_invoice_raises_inv_not_found(self):
        invoice_repo = MagicMock()
        invoice_repo.get_by_id.return_value = None
        with self.assertRaises(NotFoundException) as ctx:
            GetInvoicePdfUseCase(
                invoice_repo=invoice_repo,
                storage=MagicMock(),
                directory=MagicMock(),
                template_loader=MagicMock(),
                render_resolver=MagicMock(),
                path_resolver=MagicMock(),
            ).execute(uuid.uuid4())
        self.assertEqual(ctx.exception.code, AppErrorCode.INV_NOT_FOUND)

    def test_render_path_uses_injected_loader(self):
        invoice = _invoice()
        invoice_repo = MagicMock()
        invoice_repo.get_by_id.return_value = invoice

        directory = MagicMock()
        directory.company.return_value = SimpleNamespace(
            name='Acme', nit='1', address='',
            geo_city=None,
        )
        directory.admin_of.return_value = SimpleNamespace(
            first_name='A', last_name='B', email='a@b.c', username='a',
        )
        directory.subscription_name.return_value = 'Pro'
        directory.active_card.return_value = None

        template = MagicMock()
        template_loader = MagicMock()
        template_loader.load.return_value = template
        renderer = MagicMock()
        renderer.render.return_value = (b'%PDF-fresh', 'application/pdf')
        render_resolver = MagicMock()
        render_resolver.resolve.return_value = renderer

        result = GetInvoicePdfUseCase(
            invoice_repo=invoice_repo,
            storage=MagicMock(),
            directory=directory,
            template_loader=template_loader,
            render_resolver=render_resolver,
            path_resolver=MagicMock(),
            system_vars_builder=MagicMock(build=MagicMock(return_value={})),
        ).execute(invoice.id)

        self.assertEqual(result.blob, b'%PDF-fresh')
        template_loader.load.assert_called_once()
        render_resolver.resolve.assert_called_once()
