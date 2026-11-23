"""
GetInvoicePdfUseCase — returns the invoice PDF bytes for download.

Strategy:
    1. If the invoice already has a stored PDF (``pdf_bucket`` +
       ``pdf_object_key``, set by SendInvoiceUseCase when the document was
       delivered to the client), return that exact copy from MinIO.
    2. Otherwise render the PDF on the fly by composing the same
       ``documents/`` building blocks SendInvoiceUseCase uses, so an admin
       can still download an invoice that was never emailed (e.g. a pending
       one). Rendering is stateless here: no upload, no ``mark_pdf_sent`` —
       that timestamp means "delivered to the client", which a download is
       not.
"""
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from django.conf import settings

from core.errors import AppErrorCode, NotFoundException
from core.storage.domain.interfaces import IStorageService

from platform.features.billing.common.directory import IBillingDirectory
from platform.features.billing.commerce.invoice.application.invoice_context import (
    build_document_context,
)
from platform.features.billing.commerce.invoice.application.send_invoice import (
    DEFAULT_INVOICE_TEMPLATE_CODE,
    _promotion_from_context,
)
from platform.features.billing.commerce.invoice.domain.interfaces import IInvoiceRepository
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

_logger = logging.getLogger('billing.invoice.download')

_PDF_CONTENT_TYPE = 'application/pdf'


@dataclass
class InvoicePdf:
    blob:         bytes
    content_type: str
    filename:     str


class GetInvoicePdfUseCase:
    """Resolve the downloadable PDF for an invoice (stored copy or fresh render)."""

    def __init__(
        self,
        invoice_repo:        IInvoiceRepository,
        storage:             IStorageService,
        directory:           IBillingDirectory,
        template_loader:     TemplateLoader,
        render_resolver:     RenderResolver,
        path_resolver:       PathResolver,
        template_code:       str = DEFAULT_INVOICE_TEMPLATE_CODE,
        system_vars_builder: SystemVarsBuilder = None,
    ):
        self._invoice_repo = invoice_repo
        self._storage = storage
        self._directory = directory
        self._template_code = template_code
        self._template_loader = template_loader
        self._system_vars_builder = system_vars_builder or SystemVarsBuilder()
        self._render_resolver = render_resolver
        self._path_resolver = path_resolver

    @trace_layer('application')
    def execute(self, invoice_id: uuid.UUID) -> InvoicePdf:
        invoice = self._invoice_repo.get_by_id(invoice_id)
        if invoice is None:
            raise NotFoundException(
                AppErrorCode.INV_NOT_FOUND,
                override_detail=f'Invoice {invoice_id} not found.',
            )

        filename = f'{invoice.invoice_number}.{FORMAT_EXTENSIONS[DocumentFormat.PDF]}'

        # ── 1. Stored copy — the exact PDF delivered to the client ────────
        if invoice.pdf_bucket and invoice.pdf_object_key:
            blob = self._storage.download_file(invoice.pdf_bucket, invoice.pdf_object_key)
            return InvoicePdf(blob=blob, content_type=_PDF_CONTENT_TYPE, filename=filename)

        # ── 2. No stored copy yet — render on the fly ─────────────────────
        blob, content_type = self._render(invoice)
        return InvoicePdf(blob=blob, content_type=content_type, filename=filename)

    def _render(self, invoice):
        now = datetime.now(timezone.utc)
        company           = self._directory.company(invoice.company_id)
        admin             = self._directory.admin_of(invoice.company_id)
        subscription_name = self._directory.subscription_name(invoice.subscription_id)
        card              = self._directory.active_card(invoice.company_id)

        render_data = build_document_context(
            invoice, company=company, admin=admin,
            subscription_name=subscription_name, card=card, now=now,
            promotion=_promotion_from_context(getattr(invoice, 'metadata', None)),
        )

        template = self._template_loader.load(self._template_code)
        renderer = self._render_resolver.resolve(template, DocumentFormat.PDF)
        sys_vars = self._system_vars_builder.build(
            DocumentFormat.PDF,
            tenant=company,
            extra={
                'invoice_number': invoice.invoice_number,
                'invoice_id':     str(invoice.id),
            },
        )
        blob, content_type = renderer.render(template, render_data, sys_vars)
        _logger.info(
            'invoice_pdf_rendered',
            extra={'invoice_id': str(invoice.id), 'blob_size_bytes': len(blob)},
        )
        return blob, content_type
