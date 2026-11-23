"""
SendInvoiceUseCase — primer caso real que compone los building blocks
del módulo `documents/`.

Este archivo VIVE EN BILLING (no en documents/) porque cada feature
consumidora arma su propio pipeline. El módulo `documents/` solo
provee las piezas atómicas — no hay god-method allá.

Composición (Caso 3.1 del plan):
    invoice + company + subscription
        → TemplateLoader.load('INVOICE_DEFAULT')
        → RenderResolver.resolve(template, PDF)
        → SystemVarsBuilder.build(PDF, user, extra=invoice_data)
        → renderer.render(template, render_data, sys_vars)
        → PathResolver.resolve(template, render_data, sys_vars)
        → storage.upload(...)
        → notification.send_email(SUB_INVOICING, attachments=[pdf])
        → invoice_repo.mark_pdf_sent(...)

Toda la decisión (qué plantilla, qué datos, qué destinatario, qué
asunto) vive aquí. Si mañana aparece "remisión por correo" o
"cotización subida a Drive", se escriben en su propia feature
reutilizando los mismos building blocks + piezas nuevas.
"""
import base64
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from django.conf import settings

from core.errors import AppErrorCode, AppException, NotFoundException
from core.storage.domain.interfaces import IStorageService
from core.storage.domain.schemas import (
    PresignedUrlMethod,
    PresignedUrlSchema,
    UploadFileSchema,
)

from platform.features.billing.commerce.invoice.domain.interfaces import IInvoiceRepository
from platform.features.billing.commerce.invoice.domain.schemas import InvoiceSchema
from platform.features.billing.commerce.invoice.application.invoice_context import (
    build_document_context,
    build_email_context,
)

from platform.features.billing.common.directory import IBillingDirectory
from platform.features.communication.notification.interfaces import INotificationService

from platform.features.documents.document_template.document_template.application.blocks import (
    PathResolver,
    RenderResolver,
    SystemVarsBuilder,
    TemplateLoader,
)
from platform.features.documents.document_template.document_template.domain.enums import (
    DocumentFormat,
    FORMAT_EXTENSIONS,
)
from core.trace import trace_layer


_logger = logging.getLogger('billing.invoice.send')


def _promotion_from_context(ctx: Optional[dict]) -> Optional[dict]:
    """Extract promotion annex data from an email overlay and/or charge metadata.

    Accepts both shapes used by producers:
      * email overlay: ``promotion_serial``, ``promotion_original_amount``, …
      * charge metadata: ``promotion_serial``, ``original_amount``, ``discount_amount``, …
    """
    if not ctx:
        return None
    serial = (
        ctx.get('promotion_serial')
        or (ctx.get('email_context') or {}).get('promotion_serial')
        or ''
    )
    if not serial:
        return None

    nested = ctx.get('email_context') if isinstance(ctx.get('email_context'), dict) else {}
    vtype = (
        ctx.get('promotion_voucher_type')
        or ctx.get('voucher_type')
        or nested.get('promotion_voucher_type')
        or nested.get('voucher_type')
        or ''
    )
    original = (
        ctx.get('promotion_original_amount')
        if ctx.get('promotion_original_amount') is not None
        else ctx.get('original_amount')
    )
    if original is None:
        original = nested.get('promotion_original_amount', nested.get('original_amount'))
    discount = (
        ctx.get('promotion_discount_amount')
        if ctx.get('promotion_discount_amount') is not None
        else ctx.get('discount_amount')
    )
    if discount is None:
        discount = nested.get('promotion_discount_amount', nested.get('discount_amount'))

    try:
        discount_label = f'{Decimal(str(discount)):.2f}' if discount is not None else None
    except Exception:
        discount_label = str(discount) if discount is not None else None

    annex = (
        f'Bono promocional aplicado: {serial}'
        + (f' ({vtype})' if vtype else '')
        + (f' — Descuento: ${discount_label}' if discount_label is not None else '')
    )
    return {
        'promotion_serial': serial,
        'voucher_type': vtype,
        'original_amount': original,
        'discount_amount': discount,
        'annex': annex,
    }


DEFAULT_INVOICE_TEMPLATE_CODE = 'INVOICE_DEFAULT'   # document (PDF) template
DEFAULT_INVOICE_EMAIL_CODE    = 'SUB_INVOICING'     # existing email template (payment confirmation)


@dataclass
class SendInvoiceResult:
    invoice_id: uuid.UUID
    bucket:     str
    object_key: str
    signed_url: str
    sent_to:    str
    sent_at:    datetime


class SendInvoiceUseCase:
    """Genera el PDF de una factura, lo sube a MinIO y lo envía por correo.

    Dependencies are injected by the composition edge (ViewSet, delivery
    listener, invoice bridge). This use case never instantiates Django
    adapters or the notification facade.
    """

    def __init__(
        self,
        invoice_repo:        IInvoiceRepository,
        storage:             IStorageService,
        notification:        INotificationService,
        directory:           IBillingDirectory,
        template_loader:     TemplateLoader,
        render_resolver:     RenderResolver,
        path_resolver:       PathResolver,
        template_code:       str = DEFAULT_INVOICE_TEMPLATE_CODE,
        email_template_code: str = DEFAULT_INVOICE_EMAIL_CODE,
        system_vars_builder: Optional[SystemVarsBuilder] = None,
    ):
        self._invoice_repo  = invoice_repo
        self._storage       = storage
        self._notification = notification
        self._directory = directory
        self._template_code = template_code
        self._email_template_code = email_template_code
        self._template_loader = template_loader
        self._system_vars_builder = system_vars_builder or SystemVarsBuilder()
        self._render_resolver = render_resolver
        self._path_resolver = path_resolver

    @trace_layer('application')
    def execute(
        self,
        invoice_id:      uuid.UUID,
        recipient_email: str,
        email_context:   Optional[dict] = None,
    ) -> SendInvoiceResult:
        started = time.monotonic()
        log_extra = {
            'invoice_id':     str(invoice_id),
            'recipient':      recipient_email,
            'template_code':  self._template_code,
        }
        invoice = self._invoice_repo.get_by_id(invoice_id)
        if invoice is None:
            raise NotFoundException(
                AppErrorCode.INV_NOT_FOUND,
                override_detail=f'Invoice {invoice_id} not found.',
            )

        if not recipient_email or '@' not in recipient_email:
            raise AppException(
                AppErrorCode.INV_NO_RECIPIENT,
                override_detail=f'Invalid recipient email "{recipient_email}".',
            )

        # ── 1. Data layer: load the domain objects once, build the context
        #       that feeds BOTH the document (PDF) and the email template ──
        now = datetime.now(timezone.utc)
        company           = self._directory.company(invoice.company_id)
        admin             = self._directory.admin_of(invoice.company_id)
        subscription_name = self._directory.subscription_name(invoice.subscription_id)
        card              = self._directory.active_card(invoice.company_id)

        promotion = _promotion_from_context(email_context)
        if promotion is None:
            # Resend / download path: promo snapshot lives on the invoice row.
            promotion = _promotion_from_context(getattr(invoice, 'metadata', None))
        elif getattr(invoice, 'metadata', None):
            # Overlay wins, but fill gaps from persisted snapshot.
            merged = {**(invoice.metadata or {}), **(email_context or {})}
            promotion = _promotion_from_context(merged) or promotion

        render_data = build_document_context(
            invoice, company=company, admin=admin,
            subscription_name=subscription_name, card=card, now=now,
            promotion=promotion,
        )

        # ── 2. Compose building blocks ────────────────────────────────────
        template = self._template_loader.load(self._template_code)
        renderer = self._render_resolver.resolve(template, DocumentFormat.PDF)
        # Pass the tenant so {{ tenant_code }} resolves in the storage path
        # template (admin/invoicing/{{year}}/{{tenant_code}}/...).
        sys_vars = self._system_vars_builder.build(
            DocumentFormat.PDF,
            tenant=company,
            extra={
                'invoice_number': invoice.invoice_number,
                'invoice_id':     str(invoice.id),
            },
        )

        blob, content_type = renderer.render(template, render_data, sys_vars)

        # ── 3. Resolve where the PDF lives in MinIO ───────────────────────
        if not template.is_storable:
            raise AppException(
                AppErrorCode.DOC_NOT_STORABLE,
                override_detail=(
                    f'Template "{self._template_code}" must be storable to send invoices.'
                ),
            )

        object_key = self._path_resolver.resolve(template, render_data, sys_vars)
        bucket = template.storage_bucket or settings.DOCUMENTS_DEFAULT_BUCKET

        # ── 4. Upload (in-memory blob → MinIO, no disk involvement) ──────
        self._storage.upload_file(UploadFileSchema(
            bucket=bucket,
            object_name=object_key,
            data=blob,
            content_type=content_type,
            metadata={
                'invoice_id':     str(invoice.id),
                'invoice_number': invoice.invoice_number,
                'template_code':  self._template_code,
            },
        ))

        # ── 5. Email the PDF as attachment ───────────────────────────────
        # Always build the invoice email data layer first (real company/admin/
        # subscription/card). Callers may pass an overlay — e.g. promotion
        # annex fields or a full SUB_UPGRADE / VOUCHER_PURCHASED context.
        # Never replace the data layer with a partial dict: missing keys would
        # fall through to the template's mock_data and leak sample names.
        base_email_context = build_email_context(
            invoice, company=company, admin=admin,
            subscription_name=subscription_name, card=card, now=now,
            promotion=promotion,
        )
        if email_context is None:
            email_context = base_email_context
        else:
            email_context = {**base_email_context, **dict(email_context)}
        email_context.setdefault('invoice_number', invoice.invoice_number)

        filename = f'{invoice.invoice_number}.{FORMAT_EXTENSIONS[DocumentFormat.PDF]}'
        try:
            self._send_email(invoice, blob, content_type, filename, recipient_email, email_context)
        except Exception as exc:
            # Compensating cleanup: orphan PDF should not remain if email failed.
            try:
                self._storage.delete_file(bucket, object_key)
            except Exception:
                _logger.warning(
                    'invoice_pdf_cleanup_failed invoice=%s bucket=%s key=%s',
                    invoice.id, bucket, object_key,
                )
            if isinstance(exc, AppException):
                raise
            _logger.exception('Invoice email failed: invoice=%s recipient=%s', invoice.id, recipient_email)
            raise AppException(
                AppErrorCode.INV_EMAIL_SEND_FAILED,
                override_detail=str(exc),
            ) from exc

        # ── 6. Record the storage reference + delivery timestamp ─────────
        sent_at = datetime.now(timezone.utc)
        self._invoice_repo.mark_pdf_sent(invoice.id, bucket, object_key, sent_at)

        # ── 7. Signed URL (handy when the caller wants to show the link) ──
        signed_url = self._storage.get_presigned_url(PresignedUrlSchema(
            bucket=bucket,
            object_name=object_key,
            method=PresignedUrlMethod.GET,
        ))

        _logger.info(
            'invoice_sent',
            extra={
                **log_extra,
                'bucket':          bucket,
                'object_key':      object_key,
                'blob_size_bytes': len(blob),
                'duration_ms':     round((time.monotonic() - started) * 1000),
            },
        )

        return SendInvoiceResult(
            invoice_id=invoice.id,
            bucket=bucket,
            object_key=object_key,
            signed_url=signed_url,
            sent_to=recipient_email,
            sent_at=sent_at,
        )

    # ── Helpers ────────────────────────────────────────────────────────────

    def _send_email(
        self,
        invoice:         InvoiceSchema,
        blob:            bytes,
        content_type:    str,
        filename:        str,
        recipient_email: str,
        context:         dict,
    ) -> None:
        """Deliver the invoice PDF via the notification facade.

        Reuses the shared email pipeline (SUB_INVOICING template + sender
        identity + transport) instead of hand-rolling an EmailMessage, so
        subject/body stay admin-editable and all email goes through one path.
        The PDF blob travels as a base64 attachment (the transport contract).

        ``context`` is the SUB_INVOICING data layer (real values), so the
        template no longer falls back to its mock_data.
        """
        sent = self._notification.send_email(
            template_code=self._email_template_code,
            to=[recipient_email],
            context=context,
            attachments=[{
                'filename': filename,
                'content':  base64.b64encode(blob).decode('ascii'),
                'mimetype': content_type,
            }],
        )

        if not sent:
            raise AppException(
                AppErrorCode.INV_EMAIL_SEND_FAILED,
                override_detail=(
                    f'Notification service failed to deliver invoice '
                    f'{invoice.invoice_number} to {recipient_email}.'
                ),
            )
