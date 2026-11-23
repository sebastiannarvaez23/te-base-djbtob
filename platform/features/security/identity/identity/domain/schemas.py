import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from core.validators import (
    OptionalDateFormatValue,
    OptionalTimeFormatValue,
    DateFormatValue,
    TimeFormatValue,
)


class AdminUserPreferencesSchema(BaseModel):
    id: Optional[uuid.UUID] = None
    user_id: uuid.UUID
    language: str
    theme: str
    timezone: str
    date_format: DateFormatValue
    time_format: TimeFormatValue
    sidebar_collapsed: bool
    items_per_page: int
    notifications_enabled: bool
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UpdateAdminUserPreferencesSchema(BaseModel):
    language: Optional[str] = None
    theme: Optional[str] = None
    timezone: Optional[str] = None
    date_format: OptionalDateFormatValue = None
    time_format: OptionalTimeFormatValue = None
    sidebar_collapsed: Optional[bool] = None
    items_per_page: Optional[int] = Field(default=None, ge=5, le=200)
    notifications_enabled: Optional[bool] = None


class AdminUserProfileSchema(BaseModel):
    id: uuid.UUID
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: str
    telephone: str
    picture: Optional[str] = None
    rol_name: Optional[str] = None

    model_config = {"from_attributes": True}


class UpdateAdminUserProfileSchema(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
