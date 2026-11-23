"""Promotion email context builders + dispatch helpers.

Pure application layer: NO Django imports. Context builders are ORM-free and
dual-mode — they read either a ``VoucherSchema`` (``subscription_names`` /
``subscription_prices``) or an ORM-like object exposing a ``subscriptions``
manager. Sending is delegated to an ``INotificationPort`` and invoice concerns
to an ``IInvoiceBridgePort``; environment-dependent values (URLs, support email,
currency) arrive as an ``EmailConfig`` supplied by the composition root.
"""

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

logger = logging.getLogger('app.api')

_DEFAULT_GIFT_MESSAGE = (
    'Este bono regalo puede redimirse una única vez para activar la suscripción indicada. '
    'Una vez utilizado no podrá transferirse ni reutilizarse. '
    'Redímelo antes de la fecha de vencimiento para disfrutar de todos los beneficios de BASE.'
)

_DISCOUNT_CONDITIONS = (
    'Válido únicamente para nuevas compras o renovaciones de las suscripciones elegibles. '
    'No acumulable con otras promociones. '
    'El descuento podrá utilizarse una sola vez antes de su fecha de vencimiento.'
)


@dataclass(frozen=True)
class EmailConfig:
    """Environment-dependent email settings, supplied by composition/callers."""
    client_app_url: str = 'http://localhost:4110'
    support_email: str = 'soporte@base.local'
    currency: str = 'USD'


DEFAULT_EMAIL_CONFIG = EmailConfig()


# ── time helpers (stdlib, ORM-free) ───────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _current_year() -> str:
    return str(_now().year)


# ── dual-mode accessors (VoucherSchema | ORM-like) ────────────────────────────

def _is_orm_like(voucher) -> bool:
    return hasattr(voucher, 'subscriptions')


def _sub_names(voucher) -> list[str]:
    if _is_orm_like(voucher):
        return list(voucher.subscriptions.values_list('name', flat=True))
    return list(getattr(voucher, 'subscription_names', []) or [])


def _first_sub_name(voucher):
    names = _sub_names(voucher)
    return names[0] if names else None


def _first_sub_price(voucher):
    if _is_orm_like(voucher):
        sub = voucher.subscriptions.first()
        return Decimal(str(sub.price)) if sub is not None else None
    prices = getattr(voucher, 'subscription_prices', None) or []
    return Decimal(str(prices[0])) if prices else None


def _company_name(voucher) -> str:
    if _is_orm_like(voucher):
        company = getattr(voucher, 'company', None)
        if company is not None and getattr(voucher, 'company_id', None):
            return getattr(company, 'name', '') or ''
        return ''
    return getattr(voucher, 'company_name', '') or ''


def _is_gift(voucher) -> bool:
    return str(voucher.voucher_type) == 'GIFT'


# ── formatting helpers ────────────────────────────────────────────────────────

def _client_app_url(config: EmailConfig) -> str:
    return (config.client_app_url or DEFAULT_EMAIL_CONFIG.client_app_url).rstrip('/')


def _format_expiration_date(dt) -> str:
    return dt.strftime('%d/%m/%Y')


def _format_purchase_datetime(dt=None) -> str:
    dt = dt or _now()
    return dt.strftime('%d/%m/%Y %I:%M %p')


def _format_money(amount, currency: str | None = None) -> str:
    code = currency or DEFAULT_EMAIL_CONFIG.currency
    value = Decimal(str(amount))
    if code.upper() == 'COP':
        formatted = f'{value:,.0f}'.replace(',', '.')
        return f'${formatted} COP'
    return f'{code} {value:,.2f}'


def _voucher_type_label(voucher) -> str:
    return 'Bono Regalo' if _is_gift(voucher) else 'Bono Descuento'


def _redeem_url(voucher, config: EmailConfig) -> str:
    return f'{_client_app_url(config)}/redeem/{voucher.serial}'


def _subscription_duration_label(months: int) -> str:
    suffix = 'mes' if months == 1 else 'meses'
    return f'{months} {suffix}'


def _gift_value(voucher, *, amount_paid=None, currency: str | None = None) -> str:
    if amount_paid is not None:
        return _format_money(amount_paid, currency)
    price = _first_sub_price(voucher)
    if price is None:
        return ''
    months = getattr(voucher, 'benefit_months', None) or 1
    return _format_money(price * months, currency)


def _build_discount_subscriptions_html(voucher) -> str:
    items = ''.join(f'<li>{name}</li>' for name in _sub_names(voucher))
    return (
        "<ul style='padding-left:20px;margin:0;color:#1e3a5f;font-size:14px;'>"
        f'{items}</ul>'
    )


def _discount_caps(voucher, *, currency: str | None = None) -> tuple[str, str]:
    """Estimate maximum discount and minimum purchase from linked subscription(s)."""
    currency = currency or DEFAULT_EMAIL_CONFIG.currency
    monthly = _first_sub_price(voucher)
    if monthly is None:
        return '—', '—'
    pct = Decimal(str(getattr(voucher, 'discount_percent', 0) or 0)) / Decimal('100')
    duration = getattr(voucher, 'discount_duration_months', None) or 1
    max_discount = monthly * pct
    min_purchase = monthly * duration
    return _format_money(max_discount, currency), _format_money(min_purchase, currency)


def build_voucher_email_context(voucher, *, config: EmailConfig = DEFAULT_EMAIL_CONFIG) -> dict[str, Any]:
    return {
        'serial': voucher.serial,
        'voucher_type': str(voucher.voucher_type),
        'subscription_names': ', '.join(_sub_names(voucher)),
        'benefit_months': getattr(voucher, 'benefit_months', None) or '',
        'discount_percent': float(getattr(voucher, 'discount_percent', 0) or 0),
        'discount_duration_months': getattr(voucher, 'discount_duration_months', None),
        'redeem_valid_until': voucher.redeem_valid_until.strftime('%d/%m/%Y'),
        'company_name': _company_name(voucher),
        'notes': getattr(voucher, 'notes', '') or '',
        'current_year': _current_year(),
    }


def build_recipient_gift_email_context(
    *,
    voucher,
    buyer,
    recipient,
    amount_paid=None,
    currency: str | None = None,
    config: EmailConfig = DEFAULT_EMAIL_CONFIG,
) -> dict[str, Any]:
    subscription_name = _first_sub_name(voucher) or 'Base'
    months = getattr(voucher, 'benefit_months', None) or 1
    gift_message = (recipient.message or '').strip() or _DEFAULT_GIFT_MESSAGE
    return {
        'gift_value': _gift_value(voucher, amount_paid=amount_paid, currency=currency),
        'redeem_url': _redeem_url(voucher, config),
        'sender_name': buyer.name,
        'usage_limit': '1 uso',
        'company_name': recipient.company_name or buyer.name,
        'current_year': _current_year(),
        'gift_message': gift_message,
        'voucher_code': voucher.serial,
        'support_email': config.support_email,
        'recipient_name': recipient.name,
        'expiration_date': _format_expiration_date(voucher.redeem_valid_until),
        'subscription_name': subscription_name,
        'subscription_duration': _subscription_duration_label(months),
    }


def build_recipient_discount_email_context(
    *,
    voucher,
    buyer,
    recipient,
    amount_paid=None,
    currency: str | None = None,
    config: EmailConfig = DEFAULT_EMAIL_CONFIG,
) -> dict[str, Any]:
    currency = currency or config.currency
    pct = getattr(voucher, 'discount_percent', 0) or 0
    maximum_discount, minimum_purchase = _discount_caps(voucher, currency=currency)
    return {
        'discount': f'{pct:g}%',
        'redeem_url': _redeem_url(voucher, config),
        'sender_name': buyer.name,
        'usage_limit': '1 uso',
        'company_name': recipient.company_name or buyer.name,
        'current_year': _current_year(),
        'voucher_code': voucher.serial,
        'discount_type': 'Porcentaje',
        'subscriptions': _build_discount_subscriptions_html(voucher),
        'support_email': config.support_email,
        'recipient_name': recipient.name,
        'expiration_date': _format_expiration_date(voucher.redeem_valid_until),
        'maximum_discount': maximum_discount,
        'minimum_purchase': minimum_purchase,
        'discount_conditions': _DISCOUNT_CONDITIONS,
    }


def build_voucher_purchased_email_context(
    *,
    voucher,
    buyer,
    recipient,
    amount_paid,
    order_number: str,
    currency: str | None = None,
    config: EmailConfig = DEFAULT_EMAIL_CONFIG,
) -> dict[str, Any]:
    currency = currency or config.currency
    total_paid = _format_money(amount_paid, currency)
    return {
        'buyer_name': buyer.name,
        'total_paid': total_paid,
        'company_name': recipient.company_name or buyer.name,
        'current_year': _current_year(),
        'order_number': order_number,
        'voucher_code': voucher.serial,
        'voucher_type': _voucher_type_label(voucher),
        'purchase_date': _format_purchase_datetime(),
        'support_email': config.support_email,
        'voucher_value': total_paid,
        'invoice_number': '',
        'payment_status': 'Pagado',
        'recipient_name': recipient.name,
        'recipient_email': recipient.email,
        'purchase_detail_url': (
            f'{_client_app_url(config)}/public/gift-voucher/success?serial={voucher.serial}'
        ),
    }


def build_public_purchase_charge_metadata(*, buyer, subscription_id) -> dict[str, Any]:
    return {
        'public_purchase': True,
        'skip_invoice_email': True,
        'invoice_subscription_id': str(subscription_id),
        'recipient_email': buyer.email,
    }


# ── dispatch helpers (require ports; ORM-free) ────────────────────────────────

def dispatch_company_voucher_email(
    *,
    notifier,
    directory,
    voucher,
    config: EmailConfig = DEFAULT_EMAIL_CONFIG,
) -> None:
    """Send the admin-created company voucher email (best effort, background).

    ``notifier`` implements ``INotificationPort`` and ``directory`` implements
    ``IBillingDirectoryPort``; both are wired by the composition root.
    """
    if str(voucher.scope) != 'COMPANY' or not voucher.company_id:
        return

    admin = directory.admin_of(voucher.company_id)
    if admin is None or not getattr(admin, 'email', ''):
        return

    is_gift = _is_gift(voucher)
    template = 'GIFT_VOUCHER' if is_gift else 'DISCOUNT_VOUCHER'
    recipient = SimpleNamespace(
        name=f'{admin.first_name} {admin.last_name}'.strip() or admin.email,
        email=admin.email,
        message=getattr(voucher, 'notes', '') or '',
        company_name=directory.company_name(voucher.company_id),
    )
    buyer = SimpleNamespace(name='Base')
    if is_gift:
        ctx = build_recipient_gift_email_context(
            voucher=voucher, buyer=buyer, recipient=recipient, config=config,
        )
    else:
        ctx = build_recipient_discount_email_context(
            voucher=voucher, buyer=buyer, recipient=recipient, config=config,
        )

    def _send():
        try:
            notifier.send_email(template_code=template, to=[admin.email], context=ctx)
        except Exception as exc:  # pragma: no cover - best effort
            logger.error('dispatch_company_voucher_email failed: %s', exc)

    threading.Thread(target=_send, daemon=True).start()


def dispatch_public_purchase_buyer_invoice(
    *,
    bridge,
    notifier,
    charge_id,
    voucher,
    buyer,
    recipient,
    amount_paid,
    currency: str,
    idempotency_key: str,
    config: EmailConfig = DEFAULT_EMAIL_CONFIG,
) -> None:
    invoice_id = bridge.find_invoice_id_for_charge(charge_id)
    if invoice_id is None:
        logger.error('public purchase buyer invoice not found for charge %s', charge_id)
        return

    order_number = f'ORD-{_now():%Y%m%d}-{idempotency_key[-6:].upper()}'
    email_context = build_voucher_purchased_email_context(
        voucher=voucher,
        buyer=buyer,
        recipient=recipient,
        amount_paid=amount_paid,
        order_number=order_number,
        currency=currency,
        config=config,
    )
    email_context['invoice_number'] = bridge.invoice_number(invoice_id)

    def _send():
        try:
            bridge.send_invoice(
                invoice_id,
                buyer.email,
                email_context=email_context,
                email_template_code='VOUCHER_PURCHASED',
            )
        except Exception as exc:
            logger.warning(
                'public purchase buyer invoice with PDF failed (%s); sending email without attachment',
                exc,
            )
            _send_buyer_purchase_email_fallback(notifier, buyer.email, email_context)

    threading.Thread(target=_send, daemon=True).start()


def _send_buyer_purchase_email_fallback(notifier, recipient_email: str, email_context: dict[str, Any]) -> None:
    try:
        notifier.send_email(
            template_code='VOUCHER_PURCHASED',
            to=[recipient_email],
            context=email_context,
        )
    except Exception as exc:
        logger.error('public purchase buyer confirmation email failed: %s', exc)


def dispatch_public_purchase_emails(
    *,
    notifier,
    voucher,
    buyer,
    recipient,
    amount_paid,
    currency: str | None = None,
    config: EmailConfig = DEFAULT_EMAIL_CONFIG,
) -> None:
    currency = currency or config.currency

    if _is_gift(voucher):
        recipient_template = 'GIFT_VOUCHER'
        recipient_ctx = build_recipient_gift_email_context(
            voucher=voucher, buyer=buyer, recipient=recipient,
            amount_paid=amount_paid, currency=currency, config=config,
        )
    else:
        recipient_template = 'DISCOUNT_VOUCHER'
        recipient_ctx = build_recipient_discount_email_context(
            voucher=voucher, buyer=buyer, recipient=recipient,
            amount_paid=amount_paid, currency=currency, config=config,
        )

    def _send():
        try:
            notifier.send_email(template_code=recipient_template, to=[recipient.email], context=recipient_ctx)
        except Exception as exc:
            logger.error('public purchase recipient email failed: %s', exc)

    threading.Thread(target=_send, daemon=True).start()
