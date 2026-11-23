from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class SecurityLogInputSchema(BaseModel):
    event_type: str
    target_user_id: Optional[UUID] = None
    resource: Optional[str] = None
    detail: Optional[str] = None


class SecurityLogOutputSchema(BaseModel):
    id: str
    event_type: str
    target_user_id: Optional[UUID] = None
    resource: Optional[str] = None
    detail: Optional[str] = None
    user_id: Optional[UUID] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: str
    created_at: str

    model_config = {'from_attributes': True}
