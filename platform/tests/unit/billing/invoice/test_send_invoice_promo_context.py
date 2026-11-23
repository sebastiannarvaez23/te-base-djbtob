"""Unit tests: SendInvoiceUseCase merges promo overlay onto the email data layer."""

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock

import pytest

from platform.features.billing.commerce.invoice.application.send_invoice import SendInvoiceUseCase
from platform.features.billing.commerce.invoice.domain.schemas import InvoiceSchema

pytestmark = pytest.mark.unit


def _invoice(**overrides) -> InvoiceSchema:
    defaults = dict(
        id=uuid.uuid4(),
        invoice_number='INV-2026-PROMO',
        company_id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
        issue_date=date(2026, 7, 11),
        due_date=date(2026, 8, 11),
        total_amount=Decimal('80.00'),
        currency='USD',
        status='paid',
        notes='',
        metadata={},
    )
    defaults.update(overrides)
    return InvoiceSchema(**defaults)


def _uc(*, invoice_repo, storage, notification, directory, template_loader, renderer, path):
    render_resolver = MagicMock()
    render_resolver.resolve.return_value = renderer
    path_resolver = MagicMock()
    path_resolver.resolve.return_value = path
    return SendInvoiceUseCase(
        invoice_repo=invoice_repo,
        storage=storage,
        notification=notification,
        directory=directory,
        template_loader=template_loader,
        render_resolver=render_resolver,
        path_resolver=path_resolver,
        system_vars_builder=MagicMock(build=MagicMock(return_value={})),
    )


class TestSendInvoicePromoContextMerge(TestCase):
    """Partial promotion email_context must not wipe the real data layer."""

    def test_partial_promo_overlay_keeps_real_user_and_company(self):
        invoice = _invoice()
        invoice_repo = MagicMock()
        invoice_repo.get_by_id.return_value = invoice
        invoice_repo.mark_pdf_sent.return_value = None

        storage = MagicMock()
        storage.upload_file.return_value = None
        storage.get_presigned_url.return_value = 'https://minio/x'

        notification = MagicMock()
        notification.send_email.return_value = True

        directory = MagicMock()
        directory.company.return_value = SimpleNamespace(
            name='Acme Real S.A.S', nit='900', address='Calle 1',
            geo_city=SimpleNamespace(
                name='Bogotá',
                department=SimpleNamespace(
                    name='Cundinamarca',
                    country=SimpleNamespace(name='Colombia'),
                ),
            ),
        )
        directory.admin_of.return_value = SimpleNamespace(
            first_name='Mario', last_name='Pérez', email='mario@acme.com', username='mario',
        )
        directory.subscription_name.return_value = 'Professional'
        directory.active_card.return_value = SimpleNamespace(provider='Visa', last4='4242')

        template = MagicMock()
        template.is_storable = True
        template.storage_bucket = 'base'
        template_loader = MagicMock()
        template_loader.load.return_value = template

        renderer = MagicMock()
        renderer.render.return_value = (b'%PDF-promo', 'application/pdf')

        uc = _uc(
            invoice_repo=invoice_repo,
            storage=storage,
            notification=notification,
            directory=directory,
            template_loader=template_loader,
            renderer=renderer,
            path='invoices/x.pdf',
        )

        partial_promo = {
            'promotion_serial': 'WLGX-DSC-REAL01',
            'promotion_voucher_type': 'DISCOUNT',
            'promotion_original_amount': 100.0,
            'promotion_discount_amount': 20.0,
        }

        uc.execute(invoice.id, 'mario@acme.com', email_context=partial_promo)

        _, kwargs = notification.send_email.call_args
        ctx = kwargs['context']
        self.assertEqual(ctx['user_name'], 'Mario Pérez')
        self.assertEqual(ctx['company_name'], 'Acme Real S.A.S')
        self.assertEqual(ctx['subscription_name'], 'Professional')
        self.assertEqual(ctx['promotion_serial'], 'WLGX-DSC-REAL01')
        self.assertNotEqual(ctx['user_name'], 'Carlos Rodríguez')
        self.assertNotEqual(ctx['company_name'], 'Logística Andina S.A.S.')

        render_data = renderer.render.call_args.args[1]
        self.assertEqual(render_data['subtotal'], '$100.00 USD')
        self.assertEqual(render_data['discounts'], '$20.00 USD')
        self.assertEqual(render_data['total'], '$80.00 USD')
        self.assertIn('WLGX-DSC-REAL01', render_data['invoice_items'])
        self.assertIn('WLGX-DSC-REAL01', render_data['invoice_notes'])

    def test_resend_uses_persisted_invoice_metadata(self):
        invoice = _invoice(
            metadata={
                'promotion_serial': 'WLGX-DSC-STORED',
                'voucher_type': 'DISCOUNT',
                'original_amount': '100.00',
                'discount_amount': '20.00',
                'currency': 'USD',
            },
        )
        invoice_repo = MagicMock()
        invoice_repo.get_by_id.return_value = invoice
        invoice_repo.mark_pdf_sent.return_value = None

        storage = MagicMock()
        storage.upload_file.return_value = None
        storage.get_presigned_url.return_value = 'https://minio/x'
        notification = MagicMock()
        notification.send_email.return_value = True
        directory = MagicMock()
        directory.company.return_value = SimpleNamespace(
            name='Acme', nit='900', address='C1',
            geo_city=SimpleNamespace(
                name='Bogotá',
                department=SimpleNamespace(
                    name='',
                    country=SimpleNamespace(name='CO'),
                ),
            ),
        )
        directory.admin_of.return_value = SimpleNamespace(
            first_name='Mario', last_name='Pérez', email='mario@acme.com', username='mario',
        )
        directory.subscription_name.return_value = 'Professional'
        directory.active_card.return_value = SimpleNamespace(provider='Visa', last4='4242')

        template = MagicMock()
        template.is_storable = True
        template.storage_bucket = 'base'
        template_loader = MagicMock()
        template_loader.load.return_value = template
        renderer = MagicMock()
        renderer.render.return_value = (b'%PDF', 'application/pdf')

        uc = _uc(
            invoice_repo=invoice_repo,
            storage=storage,
            notification=notification,
            directory=directory,
            template_loader=template_loader,
            renderer=renderer,
            path='invoices/x.pdf',
        )
        uc.execute(invoice.id, 'mario@acme.com')

        render_data = renderer.render.call_args.args[1]
        self.assertEqual(render_data['subtotal'], '$100.00 USD')
        self.assertEqual(render_data['discounts'], '$20.00 USD')
        self.assertIn('WLGX-DSC-STORED', render_data['invoice_notes'])
