import uuid
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class EmailSenderSchema(BaseModel):
    id: Optional[uuid.UUID] = None
    code: str
    name: str
    email: str
    reply_to: str = ''
    is_default: bool = False
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class CreateEmailSenderSchema(BaseModel):
    code: str
    name: str
    email: str
    reply_to: str = ''
    is_default: bool = False
    is_active: bool = True


class UpdateEmailSenderSchema(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    reply_to: Optional[str] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
