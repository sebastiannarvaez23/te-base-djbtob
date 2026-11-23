import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class AdminSectionSchema(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    icon: str = ''
    order: int
    is_active: bool


class CreateAdminSectionSchema(BaseModel):
    code: str
    name: str
    icon: str = ''
    order: int = 0


class UpdateAdminSectionSchema(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    icon: Optional[str] = None
    order: Optional[int] = None
    is_active: Optional[bool] = None


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
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CreateAdminModuleSchema(BaseModel):
    code: str
    name: str
    description: str = ''
    icon: str
    route: str = ''
    section_id: uuid.UUID
    order: int = 0
    is_sidebar: bool = True


class UpdateAdminModuleSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    route: Optional[str] = None
    section_id: Optional[uuid.UUID] = None
    order: Optional[int] = None
    is_sidebar: Optional[bool] = None
    is_active: Optional[bool] = None


class AdminFeatureSchema(BaseModel):
    id: uuid.UUID
    module: str
    key: str
    label: str
    category: str
    is_active: bool


class CreateAdminFeatureSchema(BaseModel):
    module: str
    key: str
    label: str
    category: str = 'features'


class UpdateAdminFeatureSchema(BaseModel):
    module: Optional[str] = None
    key: Optional[str] = None
    label: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None


class PaginatedAdminModulesSchema(BaseModel):
    items: List[AdminModuleSchema]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginatedAdminFeaturesSchema(BaseModel):
    items: List[AdminFeatureSchema]
    total: int
    page: int
    page_size: int
    total_pages: int
