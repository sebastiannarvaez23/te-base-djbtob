import uuid
from typing import Optional
from pydantic import BaseModel


class FeatureSchema(BaseModel):
    id:        uuid.UUID
    module:    str
    key:       str
    label:     str
    category:  str
    is_active: bool

    model_config = {'from_attributes': True}


class CreateFeatureSchema(BaseModel):
    module:   str
    key:      str
    label:    str
    category: str = 'features'


class UpdateFeatureSchema(BaseModel):
    label:     Optional[str] = None
    category:  Optional[str] = None
    is_active: Optional[bool] = None
