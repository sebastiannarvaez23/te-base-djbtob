from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class TenantUserRolSchema(BaseModel):
    id: UUID
    name: str


class TenantUserSchema(BaseModel):
    id: UUID
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: str
    username: str
    telephone: str
    company_name: str
    company_nit: str
    rol: Optional[TenantUserRolSchema] = None
    is_active: bool
    # Public URL of the profile picture, or None when the user has no custom
    # picture (the UI then falls back to the initials avatar).
    picture: Optional[str] = None
