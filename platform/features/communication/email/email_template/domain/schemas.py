import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from core.email.domain.schemas import EmailAttachment
from platform.features.communication.email.email_sender.domain.schemas import EmailSenderSchema


class EmailTemplateSchema(BaseModel):
    id: Optional[uuid.UUID] = None
    code: str
    name: str
    subject: str
    body: str = ''
    html_template: str
    sender: Optional[uuid.UUID] = None
    sender_detail: Optional[EmailSenderSchema] = None
    mock_data: dict = {}
    description: str = ''
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CreateEmailTemplateSchema(BaseModel):
    code: str
    name: str
    subject: str
    body: str = ''
    html_template: str
    sender: Optional[uuid.UUID] = None
    mock_data: dict = {}
    description: str = ''
    is_active: bool = True


class UpdateEmailTemplateSchema(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    html_template: Optional[str] = None
    sender: Optional[uuid.UUID] = None
    mock_data: Optional[dict] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class SendEmailSchema(BaseModel):
    """Input for sending an email based on a template."""
    template_code: str
    to: list[str] = Field(..., min_length=1, max_length=50)
    context: dict = {}
    attachments: list[EmailAttachment] = Field(default_factory=list)
    cc: list[str] = Field(default_factory=list, max_length=50)
    bcc: list[str] = Field(default_factory=list, max_length=50)
