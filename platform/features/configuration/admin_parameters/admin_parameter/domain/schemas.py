import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

_CODE_RE = re.compile(r'^[A-Z_]+$')
_NAME_RE = re.compile(r'^[A-Za-záéíóúÁÉÍÓÚñÑüÜ ]+$')
_DESC_RE = re.compile(r'^[A-Za-záéíóúÁÉÍÓÚñÑüÜ ]*$')


class AdminParameterSchema(BaseModel):
    id: Optional[uuid.UUID] = None
    parameter_type: Optional[uuid.UUID] = None
    code: str
    name: str
    description: str = ''
    data_type: str
    value: str
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {'from_attributes': True}


class CreateAdminParameterSchema(BaseModel):
    parameter_type: uuid.UUID
    code: str
    name: str
    description: str = ''
    data_type: str
    value: str
    is_active: bool = True

    @field_validator('code')
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not (3 <= len(v) <= 20):
            raise ValueError('code must be between 3 and 20 characters')
        if not _CODE_RE.match(v):
            raise ValueError('code must contain only uppercase letters and underscores')
        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not (3 <= len(v) <= 30):
            raise ValueError('name must be between 3 and 30 characters')
        if not _NAME_RE.match(v):
            raise ValueError('name must contain only letters and spaces')
        return v

    @field_validator('description')
    @classmethod
    def validate_description(cls, v: str) -> str:
        if v and not (3 <= len(v) <= 120):
            raise ValueError('description must be between 3 and 120 characters')
        if v and not _DESC_RE.match(v):
            raise ValueError('description must contain only letters and spaces')
        return v


class UpdateAdminParameterSchema(BaseModel):
    parameter_type: Optional[uuid.UUID] = None
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    data_type: Optional[str] = None
    value: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator('code')
    @classmethod
    def validate_code(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not (3 <= len(v) <= 20):
            raise ValueError('code must be between 3 and 20 characters')
        if not _CODE_RE.match(v):
            raise ValueError('code must contain only uppercase letters and underscores')
        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not (3 <= len(v) <= 30):
            raise ValueError('name must be between 3 and 30 characters')
        if not _NAME_RE.match(v):
            raise ValueError('name must contain only letters and spaces')
        return v

    @field_validator('description')
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v and not (3 <= len(v) <= 120):
            raise ValueError('description must be between 3 and 120 characters')
        if v and not _DESC_RE.match(v):
            raise ValueError('description must contain only letters and spaces')
        return v
