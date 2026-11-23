from typing import Optional
from pydantic import BaseModel


class PerformanceLogSchema(BaseModel):
    operation: str
    duration_ms: int
    endpoint: Optional[str] = None
    method: Optional[str] = None
    db_queries: Optional[int] = None
    memory_mb: Optional[float] = None
    tags: Optional[dict] = None
