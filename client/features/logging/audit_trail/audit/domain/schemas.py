from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class AuditLogInputSchema(BaseModel):
    entity_type: str
    entity_id: str
    action: str
    changes: Optional[dict] = None
    description: Optional[str] = None


class AuditLogOutputSchema(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    action: str
    changes: Optional[dict] = None
    description: Optional[str] = None
    user_id: Optional[UUID] = None
    warehouse_id: Optional[UUID] = None
    request_id: str
    ip_address: Optional[str] = None
    created_at: str

    model_config = {'from_attributes': True}
