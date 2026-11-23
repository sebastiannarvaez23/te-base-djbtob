import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from platform.features.security.access.roles.domain.schemas import AdminRoleSchema


class AdminUserSchema(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    first_name: str
    last_name: str
    telephone: str = ''
    rol: AdminRoleSchema
    is_active: bool
    is_superuser: bool
    # Public URL of the profile picture, or None when the user has no custom
    # picture (the UI then falls back to the initials avatar).
    picture: Optional[str] = None
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateAdminUserSchema(BaseModel):
    username: str
    email: str
    first_name: str
    last_name: str
    telephone: str = ''
    password: str
    rol_id: uuid.UUID
    is_superuser: bool = False


class UpdateAdminUserSchema(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    telephone: Optional[str] = None
    password: Optional[str] = None
    rol_id: Optional[uuid.UUID] = None
    is_superuser: Optional[bool] = None
