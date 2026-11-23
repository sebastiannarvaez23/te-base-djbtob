"""Store en memoria para tests de la máquina de estados (sin PostgreSQL)."""

from __future__ import annotations

from typing import Dict, Optional
from uuid import UUID

from handbook.core.constants import CHANGE_REQUEST_PENDING
from handbook.features.docs.governance.change_request.domain.interfaces import IChangeRequestRepository
from handbook.features.docs.governance.change_request.domain.schemas import HandbookChangeRequestSchema


class InMemoryChangeRequestRepository(IChangeRequestRepository):

    def __init__(self):
        self.rows: Dict[UUID, HandbookChangeRequestSchema] = {}
        self.published: Dict[UUID, UUID] = {}
        self.discarded: list[UUID] = []

    def get(self, request_id: UUID) -> Optional[HandbookChangeRequestSchema]:
        return self.rows.get(request_id)

    def get_pending_for_page(self, page_id: UUID) -> Optional[HandbookChangeRequestSchema]:
        for row in self.rows.values():
            if row.page_id == page_id and row.status == CHANGE_REQUEST_PENDING:
                return row
        return None

    def save(self, data: HandbookChangeRequestSchema) -> HandbookChangeRequestSchema:
        self.rows[data.id] = data
        return data

    def approve(self, data: HandbookChangeRequestSchema) -> HandbookChangeRequestSchema:
        self.published[data.page_id] = data.working_version_id
        return self.save(data)

    def reject(self, data: HandbookChangeRequestSchema) -> HandbookChangeRequestSchema:
        self.discarded.append(data.working_version_id)
        return self.save(data)

    def list_pending(self, *, offset: int = 0, limit: int = 20):
        rows = [row for row in self.rows.values() if row.status == CHANGE_REQUEST_PENDING]
        return rows[offset:offset + limit], len(rows)
