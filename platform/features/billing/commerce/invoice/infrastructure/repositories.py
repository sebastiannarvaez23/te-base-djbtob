import uuid
from datetime import datetime
from typing import Optional, List

from core.query.core import PaginatedQuery, PaginatedResult

from ..domain.interfaces import IInvoiceRepository
from ..domain.schemas import (
    CreateInvoiceSchema,
    InvoiceListItemSchema,
    InvoiceSchema,
    UpdateInvoiceStatusSchema,
)
from ..models import Invoice


def _to_list_item(invoice: Invoice) -> InvoiceListItemSchema:
    return InvoiceListItemSchema(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        company_id=invoice.company_id,
        company_name=invoice.company.name,
        company_nit=invoice.company.nit,
        subscription_id=invoice.subscription_id,
        subscription_name=invoice.subscription.name,
        company_subscription_id=invoice.company_subscription_id,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
        total_amount=invoice.total_amount,
        status=invoice.status,
        notes=invoice.notes,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
    )


class DjangoInvoiceRepository(IInvoiceRepository):

    def get_all_by_company(self, company_id: uuid.UUID) -> List[InvoiceSchema]:
        qs = Invoice.objects.filter(company_id=company_id)
        return [InvoiceSchema.model_validate(inv) for inv in qs]

    def get_paginated(self, query: PaginatedQuery) -> PaginatedResult:
        qs = (
            Invoice.objects
            .select_related('company', 'subscription')
            .all()
            .order_by('-issue_date', '-created_at')
        )
        f = query.filters

        if 'invoice_number' in f:
            qs = qs.filter(invoice_number__icontains=f['invoice_number'])
        if 'company' in f:
            qs = qs.filter(company__name__icontains=f['company'])
        if 'nit' in f:
            qs = qs.filter(company__nit__icontains=f['nit'])
        if 'subscription' in f:
            qs = qs.filter(subscription__name__icontains=f['subscription'])
        if 'status' in f:
            qs = qs.filter(status=f['status'])

        total = qs.count()
        invoices = list(qs[query.offset: query.offset + query.limit])
        items = [_to_list_item(inv) for inv in invoices]
        total_pages = (total + query.page_size - 1) // query.page_size if query.page_size else 1
        return PaginatedResult(
            items=items,
            total=total,
            page=query.page,
            page_size=query.page_size,
            total_pages=total_pages,
        )

    def get_by_id(self, id: uuid.UUID) -> Optional[InvoiceSchema]:
        try:
            obj = Invoice.objects.get(id=id)
            return InvoiceSchema.model_validate(obj)
        except Invoice.DoesNotExist:
            return None

    def get_by_invoice_number(self, invoice_number: str) -> Optional[InvoiceSchema]:
        try:
            obj = Invoice.objects.get(invoice_number=invoice_number)
            return InvoiceSchema.model_validate(obj)
        except Invoice.DoesNotExist:
            return None

    def create(self, data: CreateInvoiceSchema) -> InvoiceSchema:
        obj = Invoice.objects.create(**data.model_dump())
        return InvoiceSchema.model_validate(obj)

    def update_status(self, id: uuid.UUID, data: UpdateInvoiceStatusSchema) -> Optional[InvoiceSchema]:
        try:
            obj = Invoice.objects.get(id=id)
            obj.status = data.status
            obj.save(update_fields=['status', 'updated_at'])
            return InvoiceSchema.model_validate(obj)
        except Invoice.DoesNotExist:
            return None

    def delete(self, id: uuid.UUID) -> bool:
        try:
            Invoice.objects.get(id=id).delete()
            return True
        except Invoice.DoesNotExist:
            return False

    def mark_pdf_sent(
        self,
        id: uuid.UUID,
        bucket: str,
        object_key: str,
        sent_at: datetime,
    ) -> Optional[InvoiceSchema]:
        try:
            obj = Invoice.objects.get(id=id)
            obj.pdf_bucket = bucket
            obj.pdf_object_key = object_key
            obj.pdf_sent_at = sent_at
            obj.save(update_fields=['pdf_bucket', 'pdf_object_key', 'pdf_sent_at', 'updated_at'])
            return InvoiceSchema.model_validate(obj)
        except Invoice.DoesNotExist:
            return None

    def bind_period(self, invoice_id: uuid.UUID, period_id: uuid.UUID) -> int:
        return Invoice.objects.filter(id=invoice_id).update(company_subscription_id=period_id)

    def bind_period_for_source_charge(self, charge_id: uuid.UUID, period_id: uuid.UUID) -> int:
        updated = Invoice.objects.filter(source_charge_id=charge_id).update(
            company_subscription_id=period_id,
        )
        if updated:
            return updated
        return Invoice.objects.filter(metadata__source_charge_id=str(charge_id)).update(
            company_subscription_id=period_id,
        )
