"""
Listener que enruta eventos de pagos hacia el módulo de facturación.

Es el único módulo de ``payments/`` que importa de ``invoice/`` y
``subscription/`` — el resto del dominio queda agnóstico. Si en el
futuro queremos reemplazar Invoice por otra cosa, sólo este archivo
cambia.

Política aplicada:
  * **PaymentCaptured con ``invoice_id``** → marca la Invoice como
    ``paid``.
  * **PaymentCaptured sin ``invoice_id``** → genera una Invoice nueva
    en estado ``paid`` (auto-billing), enlazada a la suscripción
    activa de la empresa.
  * **PaymentFailed con ``invoice_id``** → marca la Invoice como
    ``overdue`` (la política de dunning decide qué sigue).
  * **PaymentRefunded total con ``invoice_id``** → marca como
    ``cancelled``. Refunds parciales no tocan el estado.

Las llamadas que mutan estado salen por los use cases existentes
(``CreateInvoiceUseCase``, ``UpdateInvoiceStatusUseCase``), nunca por
ORM directo. La lectura de la suscripción activa se delega a un adapter
(``adapters.active_subscription_lookup``) para mantener este módulo libre de ORM.
"""

import logging
import uuid
from datetime import date, datetime
from typing import Optional

from core.errors import AppErrorCode, ConflictException, ServerException

from platform.features.billing.commerce.invoice.application.use_cases import (
    CreateInvoiceUseCase,
    UpdateInvoiceStatusUseCase,
)
from platform.features.billing.commerce.invoice.domain.schemas import (
    CreateInvoiceSchema,
    UpdateInvoiceStatusSchema,
)
from platform.features.billing.commerce.invoice.infrastructure.repositories import (
    DjangoInvoiceRepository,
)

from ..domain.events import (
    PaymentCanceled,
    PaymentCaptured,
    PaymentFailed,
    PaymentRefunded,
    publish,
)
from .adapters.active_subscription_lookup import get_active_company_subscription
from .events import InvoiceIssued


_logger = logging.getLogger('payments.integration.invoice')

# Charge-metadata keys persisted onto the invoice for PDF resend/download.
_INVOICE_META_KEYS = (
    'promotion_serial',
    'promotion_voucher_type',
    'voucher_type',
    'original_amount',
    'discount_amount',
    'promotion_original_amount',
    'promotion_discount_amount',
    'promotion_annex',
    'promotion_redemption_id',
    'email_context',
    'email_template_code',
    'billing_interval',
    'source_charge_id',
)


def _snapshot_invoice_metadata(event: PaymentCaptured) -> dict:
    """Persist promo (+ delivery hints) from the charge onto the invoice row."""
    meta = dict(event.metadata or {})
    snapshot: dict = {'currency': (event.currency or 'USD').upper()}
    for key in _INVOICE_META_KEYS:
        if key in meta and meta[key] is not None:
            snapshot[key] = meta[key]
    nested = meta.get('email_context')
    if isinstance(nested, dict):
        for key, value in nested.items():
            snapshot.setdefault(key, value)
    return snapshot


def _generate_invoice_number() -> str:
    """Patrón: ``INV-YYYYMM-XXXXXXXX`` (uppercase hex sin colisiones prácticas)."""
    now = datetime.utcnow()
    return f"INV-{now:%Y%m}-{uuid.uuid4().hex[:8].upper()}"


# ── Listener ──────────────────────────────────────────────────────────────────


class InvoiceBillingListener:
    """Bridge entre eventos de ``payments`` y el lifecycle de Invoice."""

    def __init__(
        self,
        invoice_repo_factory=DjangoInvoiceRepository,
        subscription_lookup=get_active_company_subscription,
        publisher=publish,
    ):
        # Inyectable para testing — defaults razonables para producción.
        self._invoice_repo_factory = invoice_repo_factory
        self._subscription_lookup = subscription_lookup
        self._publish = publisher

    # ── handlers públicos (cada uno suscrito a un PaymentDomainEvent) ──

    def on_payment_captured(self, event: PaymentCaptured) -> None:
        """
        Cargo exitoso ⇒ registra facturación.

        Camino A: el cargo ya tenía Invoice asociada → la marcamos paid.
        Camino B: no hay Invoice → se genera una nueva en estado paid.

        En ambos casos, con la factura ya resuelta, publica ``InvoiceIssued``
        para que :class:`InvoiceDeliveryListener` la envíe — sin mutar este
        evento de pago.
        """
        if event.invoice_id is not None:
            if not self._assert_invoice_currency(event):
                return
            self._mark_status(event.invoice_id, 'paid', context=f'charge {event.charge_id}')
            invoice_id = event.invoice_id
        else:
            invoice_id = self._auto_create_paid_invoice(event)

        if invoice_id is not None:
            self._announce_issued(event, invoice_id)

    def on_payment_failed(self, event: PaymentFailed) -> None:
        """Pago fallido sobre Invoice existente ⇒ marca ``overdue``."""
        if event.invoice_id is None:
            return  # nada que hacer si no había invoice asociada
        self._mark_status(
            event.invoice_id, 'overdue',
            context=f'charge {event.charge_id} failed ({event.failure_code})',
        )

    def on_payment_canceled(self, event: PaymentCanceled) -> None:
        """Cargo cancelado sobre Invoice existente ⇒ marca ``cancelled``."""
        if event.invoice_id is None:
            return
        self._mark_status(
            event.invoice_id, 'cancelled',
            context=f'charge {event.charge_id} canceled',
        )

    def on_payment_refunded(self, event: PaymentRefunded) -> None:
        """Refund total sobre Invoice existente ⇒ marca ``cancelled``."""
        if event.is_partial or event.invoice_id is None:
            return
        self._mark_status(
            event.invoice_id, 'cancelled',
            context=f'charge {event.charge_id} fully refunded',
        )

    # ── helpers internos ───────────────────────────────────────────────

    def _assert_invoice_currency(self, event: PaymentCaptured) -> bool:
        """Fail hard on charge→invoice currency drift (never leave AR unpaid after capture)."""
        charge_currency = (event.currency or '').strip().upper()
        if not charge_currency or event.invoice_id is None:
            return True
        try:
            invoice = self._invoice_repo_factory().get_by_id(event.invoice_id)
        except Exception as exc:
            _logger.exception(
                'failed to load invoice %s for currency check (charge %s)',
                event.invoice_id, event.charge_id,
            )
            raise ServerException(
                AppErrorCode.PAY_PROVIDER_ERROR,
                override_detail=(
                    f'Unable to load invoice {event.invoice_id} for currency check '
                    f'after charge {event.charge_id}.'
                ),
            ) from exc
        if invoice is None:
            return True
        raw_invoice_currency = getattr(invoice, 'currency', None)
        if not isinstance(raw_invoice_currency, str):
            return True
        invoice_currency = raw_invoice_currency.strip().upper()
        if invoice_currency and invoice_currency != charge_currency:
            _logger.error(
                'currency drift charge %s (%s) vs invoice %s (%s)',
                event.charge_id, charge_currency, event.invoice_id, invoice_currency,
            )
            raise ConflictException(
                AppErrorCode.PAY_CURRENCY_MISMATCH,
                override_detail=(
                    f'Charge currency {charge_currency} does not match invoice '
                    f'{event.invoice_id} currency {invoice_currency}.'
                ),
            )
        return True

    def _announce_issued(self, event: PaymentCaptured, invoice_id: uuid.UUID) -> None:
        """Publica ``InvoiceIssued`` con la pista de entrega tomada de la
        metadata del cargo (el productor del cargo decide la plantilla:
        SUB_UPGRADE, etc.; por defecto el delivery usa SUB_INVOICING)."""
        meta = event.metadata or {}
        # Always announce InvoiceIssued so fiscal (Neurana) can run even when
        # email delivery is intentionally skipped (e.g. voucher purchase).
        self._publish(InvoiceIssued(
            invoice_id=invoice_id,
            company_id=event.company_id,
            charge_id=event.charge_id,
            email_template_code=meta.get('email_template_code'),
            email_context=meta.get('email_context'),
            recipient_email=meta.get('recipient_email'),
            metadata=meta,
        ))

    def _mark_status(self, invoice_id: uuid.UUID, status: str, *, context: str) -> None:
        try:
            result = UpdateInvoiceStatusUseCase(self._invoice_repo_factory()).execute(
                invoice_id,
                UpdateInvoiceStatusSchema(status=status),
            )
            if result is None:
                _logger.warning(
                    'invoice %s not found while updating to %s (%s)',
                    invoice_id, status, context,
                )
        except Exception:
            _logger.exception(
                'failed to update invoice %s → %s (%s)',
                invoice_id, status, context,
            )

    def _auto_create_paid_invoice(self, event: PaymentCaptured) -> Optional[uuid.UUID]:
        """
        Crea una Invoice en ``paid`` enlazada a la suscripción activa
        de la empresa. Devuelve el id de la invoice creada o ``None``
        si no se pudo (empresa sin suscripción activa, error de BD).

        Cargos con monto ≤ 0 (p.ej. GIFT renovado con ``skip_charge`` no
        llega aquí; si un cargo $0 se captura, no emitimos factura).
        """
        from decimal import Decimal

        if Decimal(str(event.amount)) <= 0:
            _logger.info(
                'skipping invoice for zero-amount charge %s (company %s)',
                event.charge_id, event.company_id,
            )
            return None

        company_sub = self._subscription_lookup(event.company_id)
        meta = event.metadata or {}
        override_sub_id = meta.get('invoice_subscription_id')
        if override_sub_id:
            subscription_id = uuid.UUID(str(override_sub_id))
        elif company_sub is None:
            _logger.warning(
                'cannot auto-generate invoice for charge %s: '
                'company %s has no active subscription',
                event.charge_id, event.company_id,
            )
            return None
        else:
            subscription_id = company_sub.subscription_id

        today = date.today()
        snapshot = _snapshot_invoice_metadata(event)
        snapshot['source_charge_id'] = str(event.charge_id)
        period_id = getattr(company_sub, 'id', None) if company_sub is not None else None
        try:
            invoice = CreateInvoiceUseCase(self._invoice_repo_factory()).execute(
                CreateInvoiceSchema(
                    invoice_number=_generate_invoice_number(),
                    company_id=event.company_id,
                    subscription_id=subscription_id,
                    company_subscription_id=period_id,
                    source_charge_id=event.charge_id,
                    issue_date=today,
                    due_date=today,
                    total_amount=event.amount,
                    currency=(event.currency or 'USD').upper(),
                    status='paid',
                    notes=f'Auto-generated from charge {event.charge_id}',
                    metadata=snapshot,
                ),
            )
            return invoice.id
        except Exception:
            _logger.exception(
                'failed to auto-generate invoice for charge %s', event.charge_id,
            )
            return None
