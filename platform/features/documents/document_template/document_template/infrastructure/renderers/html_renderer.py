"""
HtmlDocumentRenderer — interpolates template.html_template with data
and (optionally) injects css_overrides from format_configs.HTML.
"""
from typing import Any

from pydantic import ValidationError

from core.errors import AppErrorCode, AppException, ValidationAppException

from ...domain.enums import DocumentFormat, FORMAT_CONTENT_TYPES
from ...domain.format_configs import HtmlFormatConfig
from ...domain.renderer import IDocumentRenderer
from ...domain.template_engine import ITemplateEngine
from ...domain.schemas import DocumentTemplateSchema


class HtmlDocumentRenderer(IDocumentRenderer):

    format = DocumentFormat.HTML

    def __init__(self, engine: ITemplateEngine):
        self._engine = engine

    def validate_config(self, config: dict[str, Any]) -> None:
        try:
            HtmlFormatConfig.model_validate(config)
        except ValidationError as exc:
            raise ValidationAppException(
                AppErrorCode.DOC_FORMAT_CONFIG_INVALID,
                override_detail=f'Invalid HTML config: {exc.errors()}',
            )

    def render(
        self,
        template:    DocumentTemplateSchema,
        data:        dict[str, Any],
        system_vars: dict[str, Any],
    ) -> tuple[bytes, str]:
        try:
            cfg = HtmlFormatConfig.model_validate(template.format_configs.get('HTML', {}))
        except ValidationError as exc:
            raise AppException(
                AppErrorCode.DOC_FORMAT_CONFIG_INVALID,
                override_detail=f'HTML config malformed at render time: {exc.errors()}',
            )

        body = self._engine.interpolate(template.html_template, data, system_vars)

        if cfg.css_overrides:
            html = (
                '<!doctype html><html><head><meta charset="utf-8">'
                f'<style>{cfg.css_overrides}</style>'
                f'</head><body>{body}</body></html>'
            )
        else:
            html = body

        return html.encode('utf-8'), FORMAT_CONTENT_TYPES[DocumentFormat.HTML]
