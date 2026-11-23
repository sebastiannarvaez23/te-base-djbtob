import uuid
from datetime import date, datetime
from typing import Optional

from django.db import IntegrityError
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.query.core import PaginatedQuery, PaginatedResult

from ..domain.interfaces import IRefundRequestRepository
from ..domain.schemas import AdminRefundTicketSchema, CreateRefundTicketSchema, RefundTicketSchema
from ..models import RefundRequest


_FIELDS = (
    'id', 'ticket_number', 'company_id', 'schema_name',
    'from_subscription_id', 'from_subscription_name',
    'to_subscription_id', 'to_subscription_name',
    'period_id', 'charge_id', 'amount', 'currency', 'kind', 'status',
    'payout_due_on', 'charge_refunded_before', 'gateway_refund_id',
    'failure_message', 'rejection_reason', 'requested_by_id',
    'approved_by_id', 'approved_at', 'created_at',
    'processed_at', 'completed_at',
)


def _to_schema(row: dict) -> RefundTicketSchema:
    return RefundTicketSchema(**row)


def _to_admin(row: dict) -> AdminRefundTicketSchema:
    return AdminRefundTicketSchema(**row)


class DjangoRefundRequestRepository(IRefundRequestRepository):

    def create(self, data: CreateRefundTicketSchema) -> RefundTicketSchema:
        try:
            obj = RefundRequest.objects.create(
                company_id=data.company_id,
                schema_name=data.schema_name,
                ticket_number=data.ticket_number,
                from_subscription_id=data.from_subscription_id,
                from_subscription_name=data.from_subscription_name,
                to_subscription_id=data.to_subscription_id,
                to_subscription_name=data.to_subscription_name,
                period_id=data.period_id,
                charge_id=data.charge_id,
                amount=data.amount,
                currency=data.currency,
                kind=data.kind,
                status=RefundRequest.Status.PENDING,
                payout_due_on=data.payout_due_on,
                charge_refunded_before=data.charge_refunded_before,
                requested_by_id=data.requested_by_id,
            )
        except IntegrityError:
            raise
        return _to_schema(
            RefundRequest.objects.filter(id=obj.id).values(*_FIELDS).get()
        )

    def get_by_id(self, ticket_id: uuid.UUID, company_id: uuid.UUID | None = None) -> Optional[RefundTicketSchema]:
        qs = RefundRequest.objects.filter(id=ticket_id)
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        row = qs.values(*_FIELDS).first()
        return _to_schema(row) if row else None

    def get_open(self, company_id: uuid.UUID) -> Optional[RefundTicketSchema]:
        row = (
            RefundRequest.objects
            .filter(company_id=company_id, status__in=RefundRequest.OPEN_STATUSES)
            .order_by('-created_at')
            .values(*_FIELDS)
            .first()
        )
        return _to_schema(row) if row else None

    def get_latest(self, company_id: uuid.UUID) -> Optional[RefundTicketSchema]:
        row = (
            RefundRequest.objects
            .filter(company_id=company_id)
            .order_by('-created_at')
            .values(*_FIELDS)
            .first()
        )
        return _to_schema(row) if row else None

    def last_accepted_at(self, company_id: uuid.UUID) -> Optional[datetime]:
        return (
            RefundRequest.objects
            .filter(company_id=company_id, status__in=RefundRequest.APPROVED_STATUSES)
            .annotate(when=Coalesce('approved_at', 'created_at'))
            .order_by('-when')
            .values_list('when', flat=True)
            .first()
        )

    def mark_processing(self, ticket_id: uuid.UUID) -> Optional[RefundTicketSchema]:
        now = timezone.now()
        updated = (
            RefundRequest.objects
            .filter(id=ticket_id)
            .filter(Q(status=RefundRequest.Status.ACCEPTED) | Q(status=RefundRequest.Status.FAILED))
            .update(status=RefundRequest.Status.PROCESSING, processed_at=now, failure_message='')
        )
        if not updated:
            return self.get_by_id(ticket_id)
        return self.get_by_id(ticket_id)

    def mark_completed(self, ticket_id: uuid.UUID, *, gateway_refund_id: str) -> Optional[RefundTicketSchema]:
        now = timezone.now()
        RefundRequest.objects.filter(id=ticket_id).update(
            status=RefundRequest.Status.COMPLETED,
            gateway_refund_id=gateway_refund_id or '',
            completed_at=now,
            failure_message='',
        )
        return self.get_by_id(ticket_id)

    def mark_failed(self, ticket_id: uuid.UUID, *, error: str) -> Optional[RefundTicketSchema]:
        RefundRequest.objects.filter(id=ticket_id).update(
            status=RefundRequest.Status.FAILED,
            failure_message=(error or '')[:512],
        )
        return self.get_by_id(ticket_id)

    def mark_approved(
        self,
        ticket_id: uuid.UUID,
        *,
        approved_by_id: Optional[uuid.UUID],
        payout_due_on: date,
    ) -> Optional[RefundTicketSchema]:
        now = timezone.now()
        updated = (
            RefundRequest.objects
            .filter(id=ticket_id, status=RefundRequest.Status.PENDING)
            .update(
                status=RefundRequest.Status.ACCEPTED,
                approved_at=now,
                approved_by_id=approved_by_id,
                payout_due_on=payout_due_on,
                rejection_reason='',
            )
        )
        if not updated:
            return self.get_by_id(ticket_id)
        return self.get_by_id(ticket_id)

    def mark_rejected(self, ticket_id: uuid.UUID, *, reason: str) -> Optional[RefundTicketSchema]:
        updated = (
            RefundRequest.objects
            .filter(id=ticket_id, status=RefundRequest.Status.PENDING)
            .update(
                status=RefundRequest.Status.REJECTED,
                rejection_reason=(reason or '')[:500],
            )
        )
        if not updated:
            return self.get_by_id(ticket_id)
        return self.get_by_id(ticket_id)

    def list_admin(self, query: PaginatedQuery) -> PaginatedResult:
        qs = (
            RefundRequest.objects
            .select_related('company')
            .all()
            .order_by('-created_at')
        )
        f = query.filters
        if 'ticket_number' in f:
            qs = qs.filter(ticket_number__icontains=f['ticket_number'])
        if 'company' in f:
            qs = qs.filter(company__name__icontains=f['company'])
        if 'status' in f:
            qs = qs.filter(status=f['status'])
        total = qs.count()
        rows = list(qs[query.offset: query.offset + query.limit])
        items = [_admin_from_obj(obj) for obj in rows]
        total_pages = (total + query.page_size - 1) // query.page_size if query.page_size else 1
        return PaginatedResult(
            items=items,
            total=total,
            page=query.page,
            page_size=query.page_size,
            total_pages=total_pages,
        )

    def get_admin(self, ticket_id: uuid.UUID) -> Optional[AdminRefundTicketSchema]:
        obj = (
            RefundRequest.objects
            .select_related('company')
            .filter(id=ticket_id)
            .first()
        )
        return _admin_from_obj(obj) if obj else None


def _admin_from_obj(obj: RefundRequest) -> AdminRefundTicketSchema:
    row = {field: getattr(obj, field) for field in _FIELDS}
    row['company_id'] = obj.company_id
    company = getattr(obj, 'company', None)
    return AdminRefundTicketSchema(
        **row,
        company_name=getattr(company, 'name', '') or '',
        company_nit=getattr(company, 'nit', '') or '',
    )
