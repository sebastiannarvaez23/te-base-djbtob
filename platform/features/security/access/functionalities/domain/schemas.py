import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class FunctionalitySchema(BaseModel):
    id:         uuid.UUID
    module:     str        # module.code (string, not UUID)
    key:        str
    label:      str
    category:   str
    offering:   str = 'plan'
    billing_mode: str = 'included'
    catalog_service_id: Optional[uuid.UUID] = None
    is_active:  bool
    created_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}


class CreateFunctionalitySchema(BaseModel):
    module:   str          # module code
    key:      str
    label:    str
    category: str = 'features'
    offering: str = 'plan'
    billing_mode: str = 'included'
    catalog_service_id: Optional[uuid.UUID] = None


class UpdateFunctionalitySchema(BaseModel):
    module:    Optional[str]  = None   # module code
    key:       Optional[str]  = None
    label:     Optional[str]  = None
    category:  Optional[str]  = None
    offering:  Optional[str]  = None
    billing_mode: Optional[str] = None
    catalog_service_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None


class AssignFunctionalitySchema(BaseModel):
    module: str            # module code
