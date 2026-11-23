import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ModuleSchema(BaseModel):
    id:          uuid.UUID
    code:        str
    name:        str
    description: str
    icon:        str
    route:       str
    section_id:  uuid.UUID
    section_code: str = ''
    section_name: str = ''
    section_order: int = 0
    order:       int
    is_sidebar:  bool = True
    offering: str = 'plan'
    billing_mode: str = 'included'
    catalog_service_id: Optional[uuid.UUID] = None
    is_active:   bool
    created_at:  datetime
    updated_at:  datetime

    model_config = {'from_attributes': True}

    @classmethod
    def model_validate(cls, obj, **kwargs):
        if hasattr(obj, 'section_id'):
            return super().model_validate(obj, **kwargs)
        return super().model_validate(obj, **kwargs)


class CreateModuleSchema(BaseModel):
    code:        str
    name:        str
    description: str = ''
    icon:        str
    route:       str = ''
    section_id:  uuid.UUID
    order:       int = 0
    is_sidebar:  bool = True
    offering: str = 'plan'
    billing_mode: str = 'included'
    catalog_service_id: Optional[uuid.UUID] = None


class UpdateModuleSchema(BaseModel):
    name:        Optional[str] = None
    description: Optional[str] = None
    icon:        Optional[str] = None
    route:       Optional[str] = None
    section_id:  Optional[uuid.UUID] = None
    order:       Optional[int] = None
    is_sidebar:  Optional[bool] = None
    offering: Optional[str] = None
    billing_mode: Optional[str] = None
    catalog_service_id: Optional[uuid.UUID] = None
    is_active:   Optional[bool] = None
