import uuid
from typing import Optional

from pydantic import BaseModel

from handbook.core.constants import AUDIENCE_PUBLIC, DEFAULT_LOCALE


class HandbookChunkSchema(BaseModel):
    id: Optional[uuid.UUID] = None
    page_id: uuid.UUID
    ordinal: int = 0
    heading: str = ''
    body: str
    audience: str = AUDIENCE_PUBLIC
    feature_key: Optional[str] = None
    locale: str = DEFAULT_LOCALE
    token_count: int = 0

    model_config = {'from_attributes': True}


class HandbookRetrieveHitSchema(BaseModel):
    page_id: uuid.UUID
    slug: str
    title: str
    feature_key: Optional[str] = None
    excerpt: str
    score: float = 0.0
