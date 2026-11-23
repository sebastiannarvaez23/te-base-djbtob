"""Unit tests for the invoice data-layer builders (invoice_context)."""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase

from platform.features.billing.commerce.invoice.application.invoice_context import (
    SELLER,
    build_document_context,
    build_email_context,
)


def _invoice(**o):
    d = dict(
        invoice_number='INV-2026-000154',
        company_id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
        issue_date=date(2026, 6, 28),
        due_date=date(2026, 7, 28),
        total_amount=Decimal('95.29'),
        currency='USD',
        status='paid',
        notes='',
        metadata={},
    )
    d.update(o)
    return SimpleNamespace(id=uuid.uuid4(), **d)


def _company():
    return SimpleNamespace(
        name='Acme LATAM S.A.S',
        nit='901.234.567-8',
        address='Carrera 45 #12-67',
        geo_city=SimpleNamespace(
            name='Medellín',
            department=SimpleNamespace(
                name='Antioquia',
                country=SimpleNamespace(name='Colombia'),
            ),
        ),
    )


def _admin():
    return SimpleNamespace(first_name='Mario', last_name='Pérez',
                           email='mario.perez@email.com', username='mperez')


def _card():
    return SimpleNamespace(provider='Visa', last4='4242')


_NOW = datetime(2026, 6, 28, 9, 42, tzinfo=timezone.utc)


class TestEmailContext(TestCase):

    def test_maps_real_data(self):
        ctx = build_email_context(
            _invoice(), company=_company(), admin=_admin(),
            subscription_name='Plan Professional', card=_card(), now=_NOW,
        )
        self.assertEqual(ctx['user_name'], 'Mario Pérez')
        self.assertEqual(ctx['company_name'], 'Acme LATAM S.A.S')   # buyer
        self.assertEqual(ctx['card_brand'], 'Visa')
        self.assertEqual(ctx['card_last4'], '4242')
        self.assertEqual(ctx['subscription_name'], 'Plan Professional')
        self.assertEqual(ctx['invoice_number'], 'INV-2026-000154')
        self.assertEqual(ctx['total'], 95.29)
        self.assertEqual(ctx['current_year'], 2026)
        self.assertEqual(ctx['payment_date'], '2026-06-28')
        self.assertIn('Junio 2026', ctx['billing_period'])

    def test_missing_admin_and_card_yield_empty_not_mock(self):
        ctx = build_email_context(
            _invoice(), company=_company(), admin=None,
            subscription_name=None, card=None, now=_NOW,
        )
        # explicit empties so the template does NOT fall back to mock_data
        self.assertEqual(ctx['user_name'], '')
        self.assertEqual(ctx['card_brand'], '')
        self.assertEqual(ctx['card_last4'], '')
        self.assertEqual(ctx['subscription_name'], '')


class TestDocumentContext(TestCase):

    def test_seller_is_the_billing_entity(self):
        ctx = build_document_context(
            _invoice(), company=_company(), admin=_admin(),
            subscription_name='Plan Professional', card=_card(), now=_NOW,
        )
        self.assertEqual(ctx['company_name'], SELLER['company_name'])      # seller
        self.assertEqual(ctx['company_tax_id'], SELLER['company_tax_id'])

    def test_customer_is_tenant_company_plus_admin(self):
        ctx = build_document_context(
            _invoice(), company=_company(), admin=_admin(),
            subscription_name='Plan Professional', card=_card(), now=_NOW,
        )
        self.assertEqual(ctx['customer_name'], 'Mario Pérez')
        self.assertEqual(ctx['customer_email'], 'mario.perez@email.com')
        self.assertEqual(ctx['customer_tax_id'], '901.234.567-8')
        self.assertEqual(ctx['customer_address'], 'Carrera 45 #12-67')
        self.assertIn('Medellín', ctx['customer_city'])
        self.assertIn('Colombia', ctx['customer_city'])

    def test_number_strips_inv_prefix_for_storage_path(self):
        # path template is INV-{{number}}-..., so number must not repeat 'INV-'
        ctx = build_document_context(
            _invoice(invoice_number='INV-202606-71EA68EB'),
            company=_company(), admin=_admin(),
            subscription_name='X', card=_card(), now=_NOW,
        )
        self.assertEqual(ctx['number'], '202606-71EA68EB')
        self.assertEqual(ctx['invoice_number'], 'INV-202606-71EA68EB')

    def test_amounts_and_items_and_status(self):
        ctx = build_document_context(
            _invoice(total_amount=Decimal('95.29'), status='paid'),
            company=_company(), admin=_admin(),
            subscription_name='Plan Professional', card=_card(), now=_NOW,
        )
        self.assertEqual(ctx['total'], '$95.29 USD')
        self.assertEqual(ctx['subtotal'], '$95.29 USD')
        self.assertEqual(ctx['taxes'], '$0.00 USD')
        self.assertEqual(ctx['discounts'], '$0.00 USD')
        self.assertEqual(ctx['currency'], 'USD')
        self.assertEqual(ctx['invoice_status'], 'Pagada')
        self.assertIn('Plan Professional', ctx['invoice_items'])
        self.assertEqual(ctx['payment_method'], 'Visa terminada en 4242')
        self.assertEqual(ctx['invoice_date'], '28/06/2026')

    def test_currency_from_invoice_is_used(self):
        ctx = build_document_context(
            _invoice(total_amount=Decimal('150000'), currency='COP'),
            company=_company(), admin=_admin(),
            subscription_name='Plan', card=_card(), now=_NOW,
        )
        self.assertEqual(ctx['total'], '$150,000.00 COP')
        self.assertEqual(ctx['currency'], 'COP')

    def test_promotion_breaks_down_subtotal_discount_and_notes(self):
        promo = {
            'promotion_serial': 'WLGX-DSC-INV001',
            'voucher_type': 'DISCOUNT',
            'original_amount': Decimal('100.00'),
            'discount_amount': Decimal('20.00'),
            'annex': 'Bono promocional aplicado: WLGX-DSC-INV001 (DISCOUNT) — Descuento: $20.00',
        }
        ctx = build_document_context(
            _invoice(total_amount=Decimal('80.00'), notes='Pago con tarjeta.'),
            company=_company(), admin=_admin(),
            subscription_name='Plan Professional', card=_card(), now=_NOW,
            promotion=promo,
        )
        self.assertEqual(ctx['subtotal'], '$100.00 USD')
        self.assertEqual(ctx['discounts'], '$20.00 USD')
        self.assertEqual(ctx['total'], '$80.00 USD')
        # Line item uses list price, not the charged total.
        self.assertIn('$100.00 USD', ctx['invoice_items'])
        self.assertIn('WLGX-DSC-INV001', ctx['invoice_items'])
        self.assertIn('DISCOUNT', ctx['invoice_items'])
        self.assertIn('Pago con tarjeta.', ctx['invoice_notes'])
        self.assertIn('WLGX-DSC-INV001', ctx['invoice_notes'])
        self.assertEqual(ctx['promotion_serial'], 'WLGX-DSC-INV001')
