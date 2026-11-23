import uuid
from typing import Optional
from pydantic import BaseModel


class SectionSchema(BaseModel):
    id:       uuid.UUID
    code:     str
    name:     str
    icon:     str = ''
    order:    int
    is_active: bool

    model_config = {'from_attributes': True}


class CreateSectionSchema(BaseModel):
    code:  str
    name:  str
    icon:  str = ''
    order: int = 0


class UpdateSectionSchema(BaseModel):
    code:      Optional[str] = None
    name:      Optional[str] = None
    icon:      Optional[str] = None
    order:     Optional[int] = None
    is_active: Optional[bool] = None
