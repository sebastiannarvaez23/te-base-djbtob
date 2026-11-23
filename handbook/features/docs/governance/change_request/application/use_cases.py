"""Use cases de solicitud de cambio. No publican sin approve."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from core.errors import (
    AppErrorCode,
    ConflictException,
    NotFoundException,
    ValidationAppException,
)
from core.ids import uuid7
from handbook.core.access import assert_can_approve, assert_can_propose
from handbook.core.constants import (
    CHANGE_REQUEST_APPROVED,
    CHANGE_REQUEST_PENDING,
    CHANGE_REQUEST_REJECTED,
    REASON_MAX_LENGTH,
    REASON_MIN_LENGTH,
)
from handbook.core.viewer import HandbookViewer
from handbook.features.docs.content.page.domain.interfaces import IHandbookDocumentStore
from handbook.features.docs.governance.change_request.domain.interfaces import IChangeRequestRepository
from handbook.features.docs.governance.change_request.domain.schemas import (
    ChangeRequestView,
    HandbookChangeRequestSchema,
)
from core.trace import trace_layer


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_reason(reason: str) -> str:
    text = (reason or '').strip()
    if len(text) < REASON_MIN_LENGTH or len(text) > REASON_MAX_LENGTH:
        raise ValidationAppException(AppErrorCode.HBK_REASON_REQUIRED)
    return text


def _as_uuid(value) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def describe_requests(
    rows: list[HandbookChangeRequestSchema],
    documents: IHandbookDocumentStore,
) -> list[ChangeRequestView]:
    """Enriquece las solicitudes con slug e idiomas de su página (una consulta en lote)."""
    pages = documents.page_summaries(row.page_id for row in rows)
    views = []
    for row in rows:
        page = pages.get(row.page_id)
        views.append(ChangeRequestView(
            id=row.id,
            page_id=row.page_id,
            page_slug=page.slug if page else '',
            reason=row.reason,
            status=row.status,
            proposed_by_name=row.proposed_by_name,
            created_at=row.created_at,
            locales=page.locales if page else [],
        ))
    return views


class ListPendingChangeRequestsUseCase:
    def __init__(self, requests: IChangeRequestRepository, documents: IHandbookDocumentStore):
        self.requests = requests
        self.documents = documents

    @trace_layer('application')
    def execute(self, viewer: HandbookViewer, *, offset: int = 0, limit: int = 20) -> tuple[list[ChangeRequestView], int]:
        assert_can_approve(viewer)
        rows, total = self.requests.list_pending(offset=offset, limit=limit)
        return describe_requests(rows, self.documents), total


class SubmitChangeRequestUseCase:
    def __init__(self, repository: IChangeRequestRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self,
        *,
        page_id: UUID,
        working_version_id: UUID,
        reason: str,
        viewer: HandbookViewer,
        published_version_id: UUID | None = None,
    ) -> HandbookChangeRequestSchema:
        assert_can_propose(viewer)
        reason = _normalize_reason(reason)
        if self.repository.get_pending_for_page(page_id) is not None:
            raise ConflictException(AppErrorCode.HBK_PENDING_EXISTS)
        data = HandbookChangeRequestSchema(
            id=uuid7(),
            page_id=page_id,
            working_version_id=working_version_id,
            published_version_id=published_version_id,
            reason=reason,
            status=CHANGE_REQUEST_PENDING,
            proposed_by=_as_uuid(viewer.user_id),
            created_at=_now(),
        )
        return self.repository.save(data)


class SubmitPageDraftUseCase:
    """Envía el borrador actual de una página. El id de revisión es la versión de trabajo."""

    def __init__(self, requests: IChangeRequestRepository, documents: IHandbookDocumentStore):
        self.requests = requests
        self.documents = documents

    @trace_layer('application')
    def execute(self, *, page_id: UUID, reason: str, viewer: HandbookViewer) -> HandbookChangeRequestSchema:
        revision_id = self.documents.draft_revision_id(page_id)
        if revision_id is None:
            raise ConflictException(AppErrorCode.HBK_DRAFT_REQUIRED)
        published_id = self.documents.published_revision_id(page_id)
        if published_id == revision_id:
            published_id = None
        return SubmitChangeRequestUseCase(self.requests).execute(
            page_id=page_id,
            working_version_id=revision_id,
            reason=reason,
            viewer=viewer,
            published_version_id=published_id,
        )


class ApproveChangeRequestUseCase:
    def __init__(self, repository: IChangeRequestRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self,
        request_id: UUID,
        viewer: HandbookViewer,
        *,
        review_note: str = '',
    ) -> HandbookChangeRequestSchema:
        assert_can_approve(viewer)
        current = self.repository.get(request_id)
        if current is None:
            raise NotFoundException(AppErrorCode.HBK_NOT_FOUND)
        if current.status != CHANGE_REQUEST_PENDING:
            raise ConflictException(AppErrorCode.HBK_NOT_PENDING)
        approved = current.model_copy(update={
            'status': CHANGE_REQUEST_APPROVED,
            'reviewed_by': _as_uuid(viewer.user_id),
            'review_note': (review_note or '').strip(),
            'reviewed_at': _now(),
        })
        return self.repository.approve(approved)


class RejectChangeRequestUseCase:
    def __init__(self, repository: IChangeRequestRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self,
        request_id: UUID,
        viewer: HandbookViewer,
        *,
        review_note: str = '',
    ) -> HandbookChangeRequestSchema:
        assert_can_approve(viewer)
        current = self.repository.get(request_id)
        if current is None:
            raise NotFoundException(AppErrorCode.HBK_NOT_FOUND)
        if current.status != CHANGE_REQUEST_PENDING:
            raise ConflictException(AppErrorCode.HBK_NOT_PENDING)
        rejected = current.model_copy(update={
            'status': CHANGE_REQUEST_REJECTED,
            'reviewed_by': _as_uuid(viewer.user_id),
            'review_note': (review_note or '').strip(),
            'reviewed_at': _now(),
        })
        return self.repository.reject(rejected)
