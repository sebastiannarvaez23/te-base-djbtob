"""
Invoice context builders — the *data layer* that feeds the invoice templates
with real data, analogous to the email pipeline's context.

Two distinct contexts (the variable ``company_name`` means different things
in each):
  * Document (INVOICE_DEFAULT, the PDF): ``company_*`` is the SELLER (the SaaS
    billing entity) and ``customer_*`` is the buyer (tenant company + admin).
  * Email (SUB_INVOICING): ``company_name`` is the buyer (tenant company).

These are pure functions: they receive already-loaded domain objects and
return the flat dict each template expects. Loading lives in the use case.
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from django.conf import settings


SUPPORT_EMAIL = 'soporte@base.local'

_STATUS_LABELS = {
    'paid':      'Pagada',
    'pending':   'Pendiente',
    'overdue':   'Vencida',
    'cancelled': 'Cancelada',
}

_ES_MONTHS = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
              'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']


def get_seller() -> dict[str, str]:
    """Billing entity shown on the PDF — overridable via settings/env."""
    return {
        'company_name':    getattr(settings, 'INVOICE_SELLER_NAME', 'BASE SAS'),
        'company_tax_id':  getattr(settings, 'INVOICE_SELLER_TAX_ID', '901.234.567-8'),
        'company_address': getattr(settings, 'INVOICE_SELLER_ADDRESS', 'Calle 100 #15-25'),
        'company_city':    getattr(settings, 'INVOICE_SELLER_CITY', 'Cali, Valle del Cauca, Colombia'),
    }


# Back-compat alias for tests/importers that referenced the old constant.
SELLER: dict[str, str] = get_seller()


# ── formatting helpers ────────────────────────────────────────────────────────

def _money(amount: Any, currency: str = 'USD') -> str:
    code = (currency or getattr(settings, 'INVOICE_DEFAULT_CURRENCY', 'USD') or 'USD').upper()
    return f'${Decimal(str(amount)):,.2f} {code}'

def _date(d) -> str:
    return d.strftime('%d/%m/%Y') if d else ''

def _datetime(dt: datetime) -> str:
    return dt.strftime('%d/%m/%Y %I:%M %p UTC')

def _es_month(d) -> str:
    return f'{_ES_MONTHS[d.month]} {d.year}' if d else ''

def _full_name(admin) -> str:
    if admin is None:
        return ''
    name = f'{getattr(admin, "first_name", "") or ""} {getattr(admin, "last_name", "") or ""}'.strip()
    return name or getattr(admin, 'username', '') or ''

def _card_label(card) -> str:
    if card is None:
        return ''
    brand = getattr(card, 'provider', '') or ''
    last4 = getattr(card, 'last4', '') or ''
    return f'{brand} terminada en {last4}'.strip() if (brand or last4) else ''

def _short_number(invoice_number: str) -> str:
    """Invoice number without the leading 'INV-'. The document storage path
    adds 'INV-' as a literal prefix (INV-{{number}}-...), so keeping it here
    would double it (INV-INV-...)."""
    return invoice_number[4:] if invoice_number.startswith('INV-') else invoice_number


def _invoice_currency(invoice) -> str:
    currency = getattr(invoice, 'currency', None)
    if currency:
        return str(currency).upper()
    meta = getattr(invoice, 'metadata', None) or {}
    if isinstance(meta, dict) and meta.get('currency'):
        return str(meta['currency']).upper()
    return getattr(settings, 'INVOICE_DEFAULT_CURRENCY', 'USD')


# ── context builders ──────────────────────────────────────────────────────────

def build_email_context(
    invoice,
    *,
    company,
    admin,
    subscription_name: Optional[str],
    card,
    now: datetime,
    promotion: Optional[dict] = None,
) -> dict[str, Any]:
    """Context for the SUB_INVOICING email (matches its mock_data shape)."""
    promo = promotion or {}
    original = promo.get('original_amount')
    discount = promo.get('discount_amount')
    currency = _invoice_currency(invoice)
    ctx = {
        'total':             float(invoice.total_amount),
        'currency':          currency,
        'user_name':         _full_name(admin),
        'card_brand':        getattr(card, 'provider', '') or '',
        'card_last4':        getattr(card, 'last4', '') or '',
        'company_name':      getattr(company, 'name', '') or '',
        'current_year':      now.year,
        'payment_date':      now.strftime('%Y-%m-%d'),
        'support_email':     SUPPORT_EMAIL,
        'billing_period':    f'{_es_month(invoice.issue_date)} - {_es_month(invoice.due_date)}',
        'invoice_number':    invoice.invoice_number,
        'subscription_name': subscription_name or '',
    }
    if promo:
        ctx.update({
            'promotion_serial': promo.get('promotion_serial', ''),
            'promotion_voucher_type': promo.get('voucher_type', ''),
            'promotion_original_amount': float(original) if original is not None else None,
            'promotion_discount_amount': float(discount) if discount is not None else None,
            'promotion_annex': promo.get('annex', ''),
            'has_promotion': True,
        })
    else:
        ctx['has_promotion'] = False
    return ctx


def build_document_context(
    invoice,
    *,
    company,
    admin,
    subscription_name: Optional[str],
    card,
    now: datetime,
    promotion: Optional[dict] = None,
) -> dict[str, Any]:
    """Context for the INVOICE_DEFAULT document (the PDF).

    Seller (``company_*``) comes from SELLER config. When a promotion is
    present, the line item shows the list price (original), ``discounts``
    shows the voucher amount, and ``total`` is what was charged. The promo
    annex is appended to ``invoice_notes`` (Observaciones) so it appears
    even if the HTML template has no dedicated promotion placeholders.
    """
    currency = _invoice_currency(invoice)
    total = _money(invoice.total_amount, currency)
    promo = promotion or {}
    original_amount = promo.get('original_amount')
    discount_amount = promo.get('discount_amount')
    subtotal = _money(original_amount, currency) if original_amount is not None else total
    discounts = _money(discount_amount, currency) if discount_amount is not None else _money(0, currency)
    unit_price = subtotal  # qty 1 → unit = list/original price
    from platform.features.company.tenant.company.domain.location import (
        company_location_city_line,
    )

    customer_city = company_location_city_line(company)

    item_label = subscription_name or 'Suscripción'
    serial = promo.get('promotion_serial') or ''
    if serial:
        vtype = promo.get('voucher_type') or ''
        suffix = f' — bono {serial}' + (f' ({vtype})' if vtype else '')
        item_label = f'{item_label}{suffix}'

    item_row = (
        f"<tr><td>{item_label}</td>"
        f"<td align='center'>1</td>"
        f"<td align='right'>{unit_price}</td>"
        f"<td align='right'>{unit_price}</td></tr>"
    )

    base_notes = (invoice.notes or '').strip() or 'Gracias por utilizar la base.'
    annex = (promo.get('annex') or '').strip()
    invoice_notes = f'{base_notes}\n\n{annex}'.strip() if annex else base_notes

    return {
        # seller (the SaaS billing entity)
        **get_seller(),
        'support_email':     SUPPORT_EMAIL,
        # identity / dates
        'invoice_number':    invoice.invoice_number,
        'number':            _short_number(invoice.invoice_number),  # path adds 'INV-' literally
        'invoice_status':    _STATUS_LABELS.get(invoice.status, invoice.status),
        'invoice_date':      _date(invoice.issue_date),
        'due_date':          _date(invoice.due_date),
        'payment_date':      _datetime(now),
        'generated_date':    _datetime(now),
        'current_year':      str(now.year),
        # customer (tenant company + admin)
        'customer_name':     _full_name(admin) or (getattr(company, 'name', '') or ''),
        'customer_email':    getattr(admin, 'email', '') or '',
        'customer_tax_id':   getattr(company, 'nit', '') or '',
        'customer_address':  getattr(company, 'address', '') or '',
        'customer_city':     customer_city,
        # amounts — with promotion: subtotal=list, discounts=voucher, total=charged
        'currency':          currency,
        'subtotal':          subtotal,
        'taxes':             _money(0, currency),
        'discounts':         discounts,
        'total':             total,
        # promotion annex (also mirrored into invoice_notes for PDF visibility)
        'promotion_serial':  serial,
        'promotion_annex':   annex,
        # items + notes
        'invoice_items':     item_row,
        'invoice_notes':     invoice_notes,
        # payment
        'payment_method':    _card_label(card),
        'payment_reference': '',
    }
