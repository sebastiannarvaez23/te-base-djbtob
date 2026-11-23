"""
Document renderer port.

A renderer is autonomous: it knows only its own format and its own slice
of `template.format_configs`. It does not touch storage, does not write
to disk, does not know about other renderers.

Output is always (bytes, content_type) — pure in-memory data. The
consumer (use case) decides what to do next (stream, store, attach, ...).
"""
from abc import ABC, abstractmethod
from typing import Any

from .schemas import DocumentTemplateSchema
from .enums import DocumentFormat


class IDocumentRenderer(ABC):

    format: DocumentFormat  # subclass attribute

    @abstractmethod
    def validate_config(self, config: dict[str, Any]) -> None:
        """Raise ValidationAppException if `config` (slice of format_configs) is bad."""
        ...

    @abstractmethod
    def render(
        self,
        template:    DocumentTemplateSchema,
        data:        dict[str, Any],
        system_vars: dict[str, Any],
    ) -> tuple[bytes, str]:
        """Return (blob, content_type). Pure in-memory."""
        ...
