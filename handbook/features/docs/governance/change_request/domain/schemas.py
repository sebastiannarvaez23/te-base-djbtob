import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from handbook.core.constants import CHANGE_REQUEST_PENDING


class HandbookChangeRequestSchema(BaseModel):
    id: uuid.UUID
    page_id: uuid.UUID
    working_version_id: uuid.UUID
    published_version_id: Optional[uuid.UUID] = None
    reason: str
    status: str = CHANGE_REQUEST_PENDING
    proposed_by: uuid.UUID
    proposed_by_name: str = ''
    reviewed_by: Optional[uuid.UUID] = None
    review_note: str = ''
    created_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None

    model_config = {'from_attributes': True}


class ChangeRequestView(BaseModel):
    """Solicitud lista para la bandeja del aprobador."""

    id: uuid.UUID
    page_id: uuid.UUID
    page_slug: str = ''
    reason: str
    status: str
    proposed_by_name: str = ''
    created_at: Optional[datetime] = None
    locales: list[str] = Field(default_factory=list)


class SubmitChangeRequestSchema(BaseModel):
    page_id: uuid.UUID
    working_version_id: uuid.UUID
    reason: str = Field(min_length=1)


class ReviewChangeRequestSchema(BaseModel):
    review_note: str = ''
