from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, NotFoundException
from core.storage.infrastructure.minio_storage import MinioStorageService
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication
from platform.features.billing.common.directory import DjangoBillingDirectory
from platform.features.billing.commerce.invoice.application.get_invoice_pdf import GetInvoicePdfUseCase
from platform.features.billing.commerce.invoice.application.send_invoice import SendInvoiceUseCase
from platform.features.billing.commerce.invoice.application.use_cases import (
    GetInvoicesByCompanyUseCase,
    GetInvoiceByNumberUseCase,
    CreateInvoiceUseCase,
    ListInvoicesPaginatedUseCase,
    UpdateInvoiceStatusUseCase,
    DeleteInvoiceUseCase,
)
from platform.features.billing.commerce.invoice.domain.schemas import CreateInvoiceSchema, UpdateInvoiceStatusSchema
from platform.features.billing.commerce.invoice.infrastructure.repositories import DjangoInvoiceRepository
from platform.features.billing.commerce.invoice.models import Invoice
from platform.features.billing.commerce.invoice.presentation.bodies import (
    CreateInvoiceBody,
    ResendInvoiceBody,
    UpdateInvoiceStatusBody,
)
from platform.features.billing.commerce.invoice.presentation.queries import (
    CompanyInvoiceQuery,
    InvoiceQuery,
)
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


class InvoiceViewSet(viewsets.ModelViewSet):
    """Invoice view set."""

    queryset = Invoice.objects.all()
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_repository(self):
        return DjangoInvoiceRepository()

    def _template_loader(self) -> TemplateLoader:
        return TemplateLoader(DjangoDocumentTemplateRepository())

    def _render_resolver(self) -> RenderResolver:
        return RenderResolver(get_renderer_registry())

    def _path_resolver(self) -> PathResolver:
        return PathResolver(get_template_engine())

    @validated_query(InvoiceQuery)
    def list_admin(self, request, *args, query: PaginatedQuery, **kwargs):
        result = ListInvoicesPaginatedUseCase(self._get_repository()).execute(query)
        return wrap_response({
            'items': [item.model_dump(mode='json') for item in result.items],
            'total': result.total,
            'page': result.page,
            'page_size': result.page_size,
            'total_pages': result.total_pages,
        })

    @validated_query(CompanyInvoiceQuery)
    def list_by_company(self, request, *args, query: PaginatedQuery, **kwargs):
        company_id = kwargs.get('company_id')
        results = GetInvoicesByCompanyUseCase(self._get_repository()).execute(company_id)
        # Bounded per-company list (explicit unpaginated query flag).
        return wrap_response({
            'items': [inv.model_dump(mode='json') for inv in results],
            'total': len(results),
        })

    def retrieve_by_number(self, request, *args, **kwargs):
        invoice_number = kwargs.get('invoice_number')
        result = GetInvoiceByNumberUseCase(self._get_repository()).execute(invoice_number)
        if not result:
            raise NotFoundException(AppErrorCode.INV_NOT_FOUND, override_detail='Invoice not found.')
        return wrap_response(result.model_dump(mode='json'))

    @validated_body(CreateInvoiceBody)
    def create(self, request, *args, body: dict, **kwargs):
        schema = CreateInvoiceSchema(
            invoice_number=body['invoice_number'],
            company_id=body['company'],
            subscription_id=body['subscription'],
            issue_date=body['issue_date'],
            due_date=body['due_date'],
            total_amount=body['total_amount'],
            currency=body.get('currency', 'USD'),
            status=body.get('status', 'pending'),
            notes=body.get('notes') or '',
            metadata=body.get('metadata') or {},
        )
        result = CreateInvoiceUseCase(self._get_repository()).execute(schema)
        audit_log(request, 'Invoice', result.id, 'CREATE', f'Invoice created: {result.invoice_number}')
        return wrap_response(result.model_dump(mode='json'), status_code=201, message="The item has been created successfully.")

    @validated_body(UpdateInvoiceStatusBody)
    def update_status(self, request, *args, body: dict, **kwargs):
        schema = UpdateInvoiceStatusSchema(**body)
        result = UpdateInvoiceStatusUseCase(self._get_repository()).execute(kwargs.get('pk'), schema)
        if not result:
            raise NotFoundException(AppErrorCode.INV_NOT_FOUND, override_detail='Invoice not found.')
        audit_log(request, 'Invoice', kwargs.get('pk'), 'UPDATE_STATUS', changes = body)
        return wrap_response(result.model_dump(mode='json'))

    def destroy(self, request, *args, **kwargs):
        pk = kwargs.get('pk')
        deleted = DeleteInvoiceUseCase(self._get_repository()).execute(pk)
        if not deleted:
            raise NotFoundException(AppErrorCode.INV_NOT_FOUND, override_detail='Invoice not found.')
        audit_log(request, 'Invoice', pk, 'DELETE')
        return Response(status=status.HTTP_204_NO_CONTENT)

    def download(self, request, *args, **kwargs):
        """Stream the invoice PDF as a file download.

        Returns the stored PDF when the invoice was already delivered to the
        client; otherwise renders it on the fly. No email is sent.
        """
        pk = kwargs.get('pk')
        use_case = GetInvoicePdfUseCase(
            invoice_repo=self._get_repository(),
            storage=MinioStorageService(),
            directory=DjangoBillingDirectory(),
            template_loader=self._template_loader(),
            render_resolver=self._render_resolver(),
            path_resolver=self._path_resolver(),
        )
        result = use_case.execute(pk)

        audit_log(request, 'Invoice', pk, 'DOWNLOAD', f'Invoice PDF downloaded: {result.filename}')

        response = HttpResponse(result.blob, content_type=result.content_type)
        response['Content-Disposition'] = f'attachment; filename="{result.filename}"'
        return response

    @validated_body(ResendInvoiceBody)
    def resend(self, request, *args, body: dict, **kwargs):
        """Manually regenerate the PDF and resend the invoice email.

        Triggers the same SendInvoiceUseCase that fires automatically on
        PaymentCaptured, but with an explicit recipient supplied by the
        admin. Useful when the auto-send was skipped (no recipient
        configured) or when the customer needs another copy.
        """
        pk = kwargs.get('pk')

        use_case = SendInvoiceUseCase(
            invoice_repo=self._get_repository(),
            storage=MinioStorageService(),
            notification=NotificationService(),
            directory=DjangoBillingDirectory(),
            template_loader=self._template_loader(),
            render_resolver=self._render_resolver(),
            path_resolver=self._path_resolver(),
        )
        result = use_case.execute(pk, body['recipient_email'])

        audit_log(
            request, 'Invoice', pk, 'RESEND',
            f'Invoice resent to {result.sent_to} (object_key={result.object_key})',
        )
        return wrap_response({
            'invoice_id': str(result.invoice_id),
            'bucket':     result.bucket,
            'object_key': result.object_key,
            'signed_url': result.signed_url,
            'sent_to':    result.sent_to,
            'sent_at':    result.sent_at.isoformat(),
        })
