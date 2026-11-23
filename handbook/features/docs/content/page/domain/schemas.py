import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from handbook.core.constants import (
    AUDIENCE_PUBLIC,
    DEFAULT_LOCALE,
    KIND_MANUAL,
    STATUS_DRAFT,
)


class HandbookVersionSchema(BaseModel):
    id: Optional[uuid.UUID] = None
    page_id: Optional[uuid.UUID] = None
    bucket: str = ''
    object_key: str = ''
    content_sha256: str = ''
    created_at: Optional[datetime] = None

    model_config = {'from_attributes': True}


class HandbookPageSchema(BaseModel):
    id: Optional[uuid.UUID] = None
    node_id: Optional[uuid.UUID] = None
    slug: str
    title: str
    locale: str = DEFAULT_LOCALE
    status: str = STATUS_DRAFT
    published_version_id: Optional[uuid.UUID] = None
    published_markdown: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {'from_attributes': True}


class LocaleVersionInput(BaseModel):
    locale: str
    version: str
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=2000)
    markdown: str


class SavePageDraftSchema(BaseModel):
    slug: str
    parent_id: Optional[uuid.UUID] = None
    show_in_sidebar: bool = True
    audience: str = AUDIENCE_PUBLIC
    kind: str = KIND_MANUAL
    client_feature_id: Optional[uuid.UUID] = None
    admin_feature_id: Optional[uuid.UUID] = None
    sort_order: int = Field(default=0, ge=0, le=10000)
    icon: str = ''
    menu_title: str = Field(default='', max_length=200)
    http_method: str = ''
    versions: list[LocaleVersionInput] = Field(default_factory=list)


class LocaleVersionView(BaseModel):
    id: uuid.UUID
    locale: str
    version: str
    title: str
    description: str
    markdown: str
    object_key: str
    content_sha256: str = ''
    created_at: Optional[datetime] = None


class ManagePageView(BaseModel):
    id: uuid.UUID
    slug: str
    parent_id: Optional[uuid.UUID] = None
    show_in_sidebar: bool
    audience: str
    kind: str
    client_feature_id: Optional[uuid.UUID] = None
    admin_feature_id: Optional[uuid.UUID] = None
    feature_label: str = ''
    sort_order: int
    icon: str = ''
    menu_title: str = ''
    http_method: str = ''
    status: str
    versions: list[LocaleVersionView]
    has_pending_request: bool = False


class PageSummaryView(BaseModel):
    """Identidad mínima de una página para listados (sin markdown)."""

    id: uuid.UUID
    slug: str
    locales: list[str] = Field(default_factory=list)


class CatalogNodeView(BaseModel):
    id: uuid.UUID
    parent_id: Optional[uuid.UUID] = None
    slug: str
    title: str
    locale: str
    audience: str
    feature_key: Optional[str] = None
    kind: str
    http_method: str = ''
    icon: str = ''
    status: str
    sort_order: int
    has_content: bool = True


class PublishedPageView(BaseModel):
    id: uuid.UUID
    node_id: Optional[uuid.UUID] = None
    slug: str
    title: str
    description: str = ''
    locale: str
    audience: str = AUDIENCE_PUBLIC
    feature_key: Optional[str] = None
    status: str
    published_markdown: Optional[str] = None
    document_version: str = ''
    updated_at: Optional[datetime] = None


class SearchHitView(BaseModel):
    slug: str
    title: str
    excerpt: str
    kind: str
    audience: str = AUDIENCE_PUBLIC
    feature_key: Optional[str] = None


class FeatureOptionView(BaseModel):
    id: uuid.UUID
    key: str
    label: str
    module: str
    audience: str
    category: str = 'features'
