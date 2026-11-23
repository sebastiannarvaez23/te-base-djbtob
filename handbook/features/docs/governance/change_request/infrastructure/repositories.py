"""Persistencia de solicitudes y publicación atómica de la revisión."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from django.db import transaction

from handbook.core.constants import CHANGE_REQUEST_PENDING
from handbook.features.docs.content.page.models import HandbookPage
from handbook.features.docs.governance.change_request.domain.interfaces import IChangeRequestRepository
from handbook.features.docs.governance.change_request.domain.schemas import HandbookChangeRequestSchema
from handbook.features.docs.governance.change_request.models import HandbookChangeRequest


def _to_schema(row: HandbookChangeRequest, *, proposed_by_name: str = '') -> HandbookChangeRequestSchema:
    return HandbookChangeRequestSchema(
        id=row.id,
        page_id=row.page_id,
        working_version_id=row.working_revision_id,
        published_version_id=row.page.published_revision_id,
        reason=row.reason,
        status=row.status,
        proposed_by=row.proposed_by,
        proposed_by_name=proposed_by_name,
        reviewed_by=row.reviewed_by,
        review_note=row.review_note,
        created_at=row.created_at,
        reviewed_at=row.reviewed_at,
    )


class DjangoChangeRequestRepository(IChangeRequestRepository):
    def get(self, request_id: UUID) -> Optional[HandbookChangeRequestSchema]:
        row = HandbookChangeRequest.objects.filter(pk=request_id).select_related('page').first()
        return _to_schema(row) if row else None

    def get_pending_for_page(self, page_id: UUID) -> Optional[HandbookChangeRequestSchema]:
        row = HandbookChangeRequest.objects.filter(
            page_id=page_id, status=CHANGE_REQUEST_PENDING,
        ).select_related('page').first()
        return _to_schema(row) if row else None

    def save(self, data: HandbookChangeRequestSchema) -> HandbookChangeRequestSchema:
        row, _created = HandbookChangeRequest.objects.update_or_create(
            id=data.id,
            defaults={
                'page_id': data.page_id,
                'working_revision_id': data.working_version_id,
                'reason': data.reason,
                'status': data.status,
                'proposed_by': data.proposed_by,
                'reviewed_by': data.reviewed_by,
                'review_note': data.review_note,
                'reviewed_at': data.reviewed_at,
            },
        )
        row = HandbookChangeRequest.objects.select_related('page').get(pk=row.id)
        return _to_schema(row)

    @transaction.atomic
    def approve(self, data: HandbookChangeRequestSchema) -> HandbookChangeRequestSchema:
        page = HandbookPage.objects.select_for_update().get(pk=data.page_id)
        page.published_revision_id = data.working_version_id
        if page.draft_revision_id == data.working_version_id:
            page.draft_revision_id = None
        page.save(update_fields=['published_revision', 'draft_revision', 'updated_at'])
        return self.save(data)

    def list_pending(self, *, offset: int = 0, limit: int = 20):
        from platform.features.security.identity.users.models import AdminUser
        rows = HandbookChangeRequest.objects.filter(
            status=CHANGE_REQUEST_PENDING,
        ).select_related('page').order_by('-created_at')
        total = rows.count()
        window = list(rows[offset:offset + limit])
        names = dict(AdminUser.objects.filter(
            pk__in=[row.proposed_by for row in window],
        ).values_list('id', 'username'))
        return [
            _to_schema(row, proposed_by_name=names.get(row.proposed_by, ''))
            for row in window
        ], total

    @transaction.atomic
    def reject(self, data: HandbookChangeRequestSchema) -> HandbookChangeRequestSchema:
        page = HandbookPage.objects.select_for_update().filter(pk=data.page_id).first()
        working = data.working_version_id
        if page is not None and page.draft_revision_id == working and page.published_revision_id != working:
            page.draft_revision_id = None
            page.save(update_fields=['draft_revision', 'updated_at'])
        return self.save(data)
