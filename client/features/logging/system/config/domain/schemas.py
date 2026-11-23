from typing import Optional
from pydantic import BaseModel


class LogRetentionConfigSchema(BaseModel):
    log_type: str
    enabled: bool = True
    retention_days: int = 90
    archive_enabled: bool = False
    archive_after_days: Optional[int] = 60
    max_records: Optional[int] = None
    cleanup_frequency: str = 'daily'

    model_config = {'from_attributes': True}


class LogRetentionConfigUpdateSchema(BaseModel):
    enabled: Optional[bool] = None
    retention_days: Optional[int] = None
    archive_enabled: Optional[bool] = None
    archive_after_days: Optional[int] = None
    max_records: Optional[int] = None
    cleanup_frequency: Optional[str] = None
