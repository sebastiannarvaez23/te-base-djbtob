"""
Building blocks for document generation.

Each block does ONE thing. Consumers (use cases living in their own
feature modules — billing, quotations, etc.) compose blocks as needed.

There is intentionally no orchestrator / facade / god-method here.
"""
from .path_resolver import PathResolver
from .render_resolver import RenderResolver
from .system_vars_builder import SystemVarsBuilder
from .template_loader import TemplateLoader

__all__ = [
    'PathResolver',
    'RenderResolver',
    'SystemVarsBuilder',
    'TemplateLoader',
]
