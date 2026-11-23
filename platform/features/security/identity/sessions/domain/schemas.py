from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class SessionSchema(BaseModel):
    id: str
    user_id: UUID
    username: str
    user_full_name: str
    company_id: Optional[UUID] = None
    company_name: Optional[str] = None
    ip_address: str
    user_agent: str
    created_at: datetime
    last_activity: datetime
    expires_at: datetime
    is_active: bool
