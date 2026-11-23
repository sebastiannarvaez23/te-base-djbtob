from typing import Optional
from pydantic import BaseModel


class ErrorLogSchema(BaseModel):
    level: str
    error_code: Optional[str] = None
    exception_type: str
    message: str
    stacktrace: Optional[str] = None
    module: Optional[str] = None
