"""
Listener that delivers the invoice PDF once an invoice is issued.

Reacts to :class:`InvoiceIssued`, published by
:class:`InvoiceBillingListener` after the invoice is in DB (either
pre-existing and marked paid, or auto-created). Reacting to that billing
event (instead of ``PaymentCaptured``) means we never depend on event
mutation or handler ordering.

Recipient resolution:
  1. The company's admin user (single per company — the registration User
     whose role is 'Administrator'). This is the intended recipient.
  2. event.recipient_email (explicit override, e.g. a resend).
  3. settings.INVOICE_FALLBACK_RECIPIENT (operator-level fallback).
  4. Otherwise skip silently — listener exceptions never break the
     payment flow (see _EventBus.publish).
"""
import logging
import uuid
from typing import Optional

from django.conf import settings

from platform.features.billing.commerce.invoice.application.send_invoice import SendInvoiceUseCase
from platform.features.billing.commerce.invoice.infrastructure.repositories import (
    DjangoInvoiceRepository,
)
from platform.features.billing.common.directory import DjangoBillingDirectory
from platform.features.communication.notification.service import NotificationService
from platform.features.documents.document_template.document_template.application.blocks import (
    PathResolver,
    RenderResolver,
    TemplateLoader,
)
from platform.features.documents.document_template.document_template.infrastructure.renderer_registry import (
    get_renderer_registry,
    get_template_engine,
)
from platform.features.documents.document_template.document_template.infrastructure.repositories import (
    DjangoDocumentTemplateRepository,
)
from core.storage.infrastructure.minio_storage import MinioStorageService

from .events import InvoiceIssued


def _default_template_loader() -> TemplateLoader:
    return TemplateLoader(DjangoDocumentTemplateRepository())


def _default_render_resolver() -> RenderResolver:
    return RenderResolver(get_renderer_registry())


def _default_path_resolver() -> PathResolver:
    return PathResolver(get_template_engine())


_logger = logging.getLogger('billing.payments.invoice_delivery')

# Charge-metadata / email-overlay keys that describe an applied promotion.
_PROMO_KEYS = (
    'promotion_serial',
    'promotion_voucher_type',
    'voucher_type',
    'original_amount',
    'discount_amount',
    'promotion_original_amount',
    'promotion_discount_amount',
    'promotion_annex',
)


def _merge_promo_into_email_context(
    email_context: Optional[dict],
    metadata: Optional[dict],
) -> Optional[dict]:
    """Ensure promotion fields from charge metadata reach SendInvoiceUseCase.

    Producers put voucher details both at the metadata root and inside
    ``email_context``. Delivery must surface them in one overlay so the PDF
    data layer (``build_document_context``) can show subtotal/discount/annex.
    """
    meta = dict(metadata or {})
    overlay = dict(email_context or {})
    nested = meta.get('email_context')
    if isinstance(nested, dict):
        for key, value in nested.items():
            overlay.setdefault(key, value)
    for key in _PROMO_KEYS:
        if key in meta and key not in overlay:
            overlay[key] = meta[key]
    return overlay or None


def _admin_email_from_directory(company_id: uuid.UUID) -> Optional[str]:
    """Resolve company admin email via the billing directory port."""
    admin = DjangoBillingDirectory().admin_of(company_id)
    email = getattr(admin, 'email', None) if admin is not None else None
    return email if isinstance(email, str) and '@' in email else None


class InvoiceDeliveryListener:
    """Send the invoice PDF by email after a payment is captured."""

    def __init__(
        self,
        invoice_repo_factory=DjangoInvoiceRepository,
        storage_factory=MinioStorageService,
        notification_factory=NotificationService,
        directory_factory=DjangoBillingDirectory,
        template_loader_factory=_default_template_loader,
        render_resolver_factory=_default_render_resolver,
        path_resolver_factory=_default_path_resolver,
        admin_email_lookup=_admin_email_from_directory,
    ):
        self._invoice_repo_factory = invoice_repo_factory
        self._storage_factory = storage_factory
        self._notification_factory = notification_factory
        self._directory_factory = directory_factory
        self._template_loader_factory = template_loader_factory
        self._render_resolver_factory = render_resolver_factory
        self._path_resolver_factory = path_resolver_factory
        self._admin_email_lookup = admin_email_lookup

    def on_invoice_issued(self, event: InvoiceIssued) -> None:
        invoice_id = event.invoice_id  # always set on InvoiceIssued
        meta = event.metadata or {}
        if meta.get('skip_invoice_email'):
            return

        recipient = self._resolve_recipient(event)
        if not recipient:
            _logger.warning(
                'invoice_delivery: no recipient email for invoice %s '
                '(charge %s, company %s). Company has no active admin user; '
                'set INVOICE_FALLBACK_RECIPIENT or include recipient_email '
                'in charge metadata.',
                invoice_id, event.charge_id, event.company_id,
            )
            return

        # The producer of the charge routed the invoice email via the charge
        # metadata, which billing carried onto InvoiceIssued: e.g. an upgrade
        # sets email_template_code='SUB_UPGRADE' + an email_context. Default =
        # SUB_INVOICING.
        #
        # Promotion fields may live on the charge metadata root
        # (original_amount / discount_amount / promotion_serial) and/or inside
        # email_context. Merge both so the PDF data layer sees the voucher.
        template_code = event.email_template_code
        email_context = _merge_promo_into_email_context(
            event.email_context, event.metadata,
        )

        try:
            kwargs = {'email_template_code': template_code} if template_code else {}
            use_case = SendInvoiceUseCase(
                invoice_repo=self._invoice_repo_factory(),
                storage=self._storage_factory(),
                notification=self._notification_factory(),
                directory=self._directory_factory(),
                template_loader=self._template_loader_factory(),
                render_resolver=self._render_resolver_factory(),
                path_resolver=self._path_resolver_factory(),
                **kwargs,
            )
            result = use_case.execute(invoice_id, recipient, email_context=email_context)
            _logger.info(
                'invoice_delivery: sent invoice %s to %s (object_key=%s)',
                result.invoice_id, result.sent_to, result.object_key,
            )
        except Exception:
            _logger.exception(
                'invoice_delivery: failed for invoice %s charge %s',
                invoice_id, event.charge_id,
            )

    # ── Helpers ─────────────────────────────────────────────────────────

    def _resolve_recipient(self, event: InvoiceIssued) -> Optional[str]:
        # Primary target: the company's admin user (single per company).
        admin_email = self._admin_email_lookup(event.company_id)
        if isinstance(admin_email, str) and '@' in admin_email:
            return admin_email
        # Fallbacks: an explicit override on the event, then operator setting.
        explicit = event.recipient_email
        if isinstance(explicit, str) and '@' in explicit:
            return explicit
        fallback = getattr(settings, 'INVOICE_FALLBACK_RECIPIENT', '')
        return fallback if fallback and '@' in fallback else None
