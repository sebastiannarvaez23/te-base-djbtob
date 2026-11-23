from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class FeatureSchema(BaseModel):
    key: str
    module: str
    label: str
    category: str

    model_config = {'from_attributes': True}


class RoleSchema(BaseModel):
    id: UUID
    name: str
    description: str = ''
    is_active: bool = True
    is_generic: bool = False
    is_editable: bool = True
    features: list[str] = []
    modules: list[str] = []

    model_config = {'from_attributes': True}


class CreateRoleSchema(BaseModel):
    name: str
    description: str = ''
    company_id: UUID


class CreateGenericRoleSchema(BaseModel):
    name: str
    description: str = ''


class UpdateRoleSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class UpdateRoleFeaturesSchema(BaseModel):
    feature_keys: list[str]
    module_codes: list[str] = []
