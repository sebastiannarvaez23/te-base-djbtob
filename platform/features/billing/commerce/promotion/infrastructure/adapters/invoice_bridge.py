"""Bridge to the invoice feature (lookup + send with PDF)."""

import uuid
from typing import Optional

from platform.features.billing.commerce.promotion.domain.interfaces import IInvoiceBridgePort


class DjangoInvoiceBridge(IInvoiceBridgePort):

    def find_invoice_id_for_charge(self, charge_id: uuid.UUID) -> Optional[uuid.UUID]:
        from platform.features.billing.commerce.invoice.models import Invoice
        invoice = (
            Invoice.objects
            .filter(notes__contains=str(charge_id))
            .order_by('-issue_date')
            .first()
        )
        return invoice.id if invoice else None

    def invoice_number(self, invoice_id: uuid.UUID) -> str:
        from platform.features.billing.commerce.invoice.models import Invoice
        invoice = Invoice.objects.filter(id=invoice_id).first()
        return getattr(invoice, 'invoice_number', '') if invoice else ''

    def send_invoice(
        self,
        invoice_id: uuid.UUID,
        recipient_email: str,
        *,
        email_context: Optional[dict] = None,
        email_template_code: Optional[str] = None,
    ) -> None:
        from core.storage.infrastructure.minio_storage import MinioStorageService
        from platform.features.billing.common.directory import DjangoBillingDirectory
        from platform.features.billing.commerce.invoice.application.send_invoice import SendInvoiceUseCase
        from platform.features.billing.commerce.invoice.infrastructure.repositories import DjangoInvoiceRepository
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

        SendInvoiceUseCase(
            invoice_repo=DjangoInvoiceRepository(),
            storage=MinioStorageService(),
            notification=NotificationService(),
            directory=DjangoBillingDirectory(),
            template_loader=TemplateLoader(DjangoDocumentTemplateRepository()),
            render_resolver=RenderResolver(get_renderer_registry()),
            path_resolver=PathResolver(get_template_engine()),
            email_template_code=email_template_code or 'VOUCHER_PURCHASED',
        ).execute(invoice_id, recipient_email, email_context=email_context)
