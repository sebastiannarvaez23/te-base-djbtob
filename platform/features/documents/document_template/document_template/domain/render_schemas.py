"""
Render-flow schemas. Used by building blocks and consumers.
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class PreviewRenderRequest(BaseModel):
    """Payload accepted by the preview endpoint."""
    model_config = ConfigDict(extra='forbid')

    data:   dict[str, Any] = {}
    format: str                              # validated against DocumentFormat at the boundary


class StorageRef(BaseModel):
    """Reference to a stored document in MinIO (returned by storable flows)."""
    model_config = ConfigDict(extra='forbid')

    bucket:                  str
    object_key:              str
    signed_url:              str
    signed_url_expires_at:   datetime


class RenderResult(BaseModel):
    """In-memory render result. Consumers decide what to do with the blob."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    blob:         bytes
    content_type: str
    filename:     str
    storage:      Optional[StorageRef] = None
