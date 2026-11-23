import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from handbook.core.constants import (
    AUDIENCE_PUBLIC,
    DEFAULT_LOCALE,
    KIND_MANUAL,
    STATUS_DRAFT,
)


class HandbookNodeSchema(BaseModel):
    """Nodo del árbol (espacio o sección) con ACL por audiencia y feature_key."""

    id: Optional[uuid.UUID] = None
    parent_id: Optional[uuid.UUID] = None
    slug: str
    title: str
    locale: str = DEFAULT_LOCALE
    audience: str = AUDIENCE_PUBLIC
    feature_key: Optional[str] = None
    kind: str = KIND_MANUAL
    status: str = STATUS_DRAFT
    sort_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {'from_attributes': True}
