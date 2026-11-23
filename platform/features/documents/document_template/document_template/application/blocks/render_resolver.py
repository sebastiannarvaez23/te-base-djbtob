"""
RenderResolver — enforces the synchronization invariant at request time.

Given (template, format), verifies that ALL three are aligned:
  1. format is in template.allowed_formats
  2. template.format_configs has an entry for format
  3. registry has a renderer for format

Returns the renderer if everything matches, raises a typed exception
otherwise. This is the gate every render path must go through.
"""
from core.errors import AppErrorCode, AppException

from ...domain.enums import DocumentFormat
from ...domain.renderer import IDocumentRenderer
from ...infrastructure.renderer_registry import RendererRegistry
from ...domain.schemas import DocumentTemplateSchema


class RenderResolver:

    def __init__(self, registry: RendererRegistry):
        self._registry = registry

    def resolve(self, template: DocumentTemplateSchema, format: DocumentFormat) -> IDocumentRenderer:
        fmt_value = format.value

        if fmt_value not in (template.allowed_formats or []):
            raise AppException(
                AppErrorCode.DOC_FORMAT_NOT_ALLOWED,
                override_detail=(
                    f'Template "{template.code}" does not allow format {fmt_value}. '
                    f'Allowed: {template.allowed_formats}'
                ),
            )

        if fmt_value not in (template.format_configs or {}):
            raise AppException(
                AppErrorCode.DOC_FORMAT_CONFIG_MISSING,
                override_detail=(
                    f'Template "{template.code}" allows format {fmt_value} but has '
                    f'no entry in format_configs for it.'
                ),
            )

        return self._registry.get(format)
