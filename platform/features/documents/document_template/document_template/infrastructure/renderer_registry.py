"""
RendererRegistry — process-wide map of DocumentFormat → IDocumentRenderer.

Constructed once at AppConfig.ready(). Consumers obtain instances via
`get_renderer_registry()`. This is the only "global" in the module;
everything else stays composable.
"""
from typing import Optional

from core.errors import AppErrorCode, AppException

from ..domain.enums import DocumentFormat
from ..domain.renderer import IDocumentRenderer
from ..domain.template_engine import ITemplateEngine


class RendererRegistry:

    def __init__(self):
        self._renderers: dict[DocumentFormat, IDocumentRenderer] = {}

    def register(self, renderer: IDocumentRenderer) -> None:
        self._renderers[renderer.format] = renderer

    def get(self, format: DocumentFormat) -> IDocumentRenderer:
        renderer = self._renderers.get(format)
        if renderer is None:
            raise AppException(
                AppErrorCode.DOC_RENDERER_NOT_REGISTERED,
                override_detail=f'No renderer registered for format {format.value}.',
            )
        return renderer

    def registered_formats(self) -> list[DocumentFormat]:
        return list(self._renderers.keys())


_registry: Optional[RendererRegistry] = None
_engine:   Optional[ITemplateEngine]  = None


def get_renderer_registry() -> RendererRegistry:
    if _registry is None:
        raise RuntimeError(
            'RendererRegistry has not been initialized. '
            'Ensure document_template AppConfig.ready() has run.'
        )
    return _registry


def get_template_engine() -> ITemplateEngine:
    """The canonical engine instance — shared by all building blocks."""
    if _engine is None:
        raise RuntimeError(
            'TemplateEngine has not been initialized. '
            'Ensure document_template AppConfig.ready() has run.'
        )
    return _engine


def _set_registry(registry: RendererRegistry, engine: ITemplateEngine) -> None:
    """Internal — only AppConfig.ready() should call this."""
    global _registry, _engine
    _registry = registry
    _engine   = engine
