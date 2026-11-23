from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class IntegrationLogInputSchema(BaseModel):
    system: str
    direction: str
    endpoint: str
    method: str
    request_body: Optional[dict] = None
    response_body: Optional[dict] = None
    status_code: Optional[int] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None


class IntegrationLogOutputSchema(BaseModel):
    id: str
    system: str
    direction: str
    endpoint: str
    method: str
    status_code: Optional[int] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    user_id: Optional[UUID] = None
    warehouse_id: Optional[UUID] = None
    request_id: str
    created_at: str

    model_config = {'from_attributes': True}
