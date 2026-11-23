import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import Any, Optional


class DocumentTemplateListItemSchema(BaseModel):
    """Lightweight row for admin tables — no HTML/mock/config payloads."""
    id: uuid.UUID
    code: str
    name: str
    kind: str
    description: str = ''
    is_active: bool = True
    is_storable: bool = False

    model_config = {"from_attributes": True}


class DocumentTemplateSchema(BaseModel):
    id: Optional[uuid.UUID] = None
    code: str
    name: str
    kind: str
    html_template: str
    mock_data: dict = {}
    description: str = ''
    is_active: bool = True

    allowed_formats:       list[str] = []
    default_format:        str       = 'PDF'
    format_configs:        dict[str, Any] = {}
    is_storable:           bool      = False
    storage_bucket:        str       = ''
    storage_path_template: str       = ''

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CreateDocumentTemplateSchema(BaseModel):
    code: str
    name: str
    kind: str
    html_template: str
    mock_data: dict = {}
    description: str = ''
    is_active: bool = True

    allowed_formats:       list[str] = []
    default_format:        str       = 'PDF'
    format_configs:        dict[str, Any] = {}
    is_storable:           bool      = False
    storage_bucket:        str       = ''
    storage_path_template: str       = ''


class UpdateDocumentTemplateSchema(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    kind: Optional[str] = None
    html_template: Optional[str] = None
    mock_data: Optional[dict] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

    allowed_formats:       Optional[list[str]] = None
    default_format:        Optional[str]       = None
    format_configs:        Optional[dict[str, Any]] = None
    is_storable:           Optional[bool]      = None
    storage_bucket:        Optional[str]       = None
    storage_path_template: Optional[str]       = None
