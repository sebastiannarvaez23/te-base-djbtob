from typing import Optional
from pydantic import BaseModel


class SystemLogSchema(BaseModel):
    level: str
    component: str
    message: str
    metadata: Optional[dict] = None
