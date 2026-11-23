import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class AdminRoleSchema(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    is_active: bool
    is_generic: bool = False
    is_editable: bool = True
    features: List[str] = Field(default_factory=list)
    modules: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FeatureCatalogItemSchema(BaseModel):
    key: str
    module: str
    label: str
    category: str


class AdminModuleSchema(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str = ''
    icon: str
    route: str
    section_id: uuid.UUID
    section_code: str
    section_name: str
    section_order: int
    order: int
    is_sidebar: bool = True
    offering: str = 'plan'
    billing_mode: str = 'included'
    catalog_service_id: Optional[uuid.UUID] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CreateAdminRoleSchema(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True


class UpdateAdminRoleSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class UpdateAdminRoleFeaturesSchema(BaseModel):
    feature_keys: List[str]
    module_codes: List[str] = Field(default_factory=list)
