"""
PdfDocumentRenderer — assembles the HTML document and delegates the
HTML→PDF conversion to an injected IPdfConverter.

This class holds only document-assembly policy: interpolate the template,
stitch header/body/footer, and map the PDF config onto engine-agnostic
conversion options. It knows nothing about Chromium, Playwright or any
concrete PDF engine — that lives behind IPdfConverter, so render() is pure
and unit-testable with a fake converter.

`header_html` / `footer_html` from format_configs.PDF are injected into the
document body rather than the engine's native header/footer, which would
require separate margin reservations.
"""
from typing import Any

from pydantic import ValidationError

from core.errors import AppErrorCode, AppException, ValidationAppException

from ...domain.enums import DocumentFormat, FORMAT_CONTENT_TYPES
from ...domain.format_configs import PdfFormatConfig
from ...domain.pdf_converter import IPdfConverter
from ...domain.renderer import IDocumentRenderer
from ...domain.template_engine import ITemplateEngine
from ...domain.schemas import DocumentTemplateSchema


# Our lowercase `page_size` config values → the engine-agnostic paper-format
# names expected by IPdfConverter. Unknown sizes fall back to Letter.
_PAGE_FORMATS = {
    'letter': 'Letter',
    'a4':     'A4',
    'legal':  'Legal',
}


class PdfDocumentRenderer(IDocumentRenderer):

    format = DocumentFormat.PDF

    def __init__(self, engine: ITemplateEngine, converter: IPdfConverter):
        self._engine = engine
        self._converter = converter

    def validate_config(self, config: dict[str, Any]) -> None:
        try:
            PdfFormatConfig.model_validate(config)
        except ValidationError as exc:
            raise ValidationAppException(
                AppErrorCode.DOC_FORMAT_CONFIG_INVALID,
                override_detail=f'Invalid PDF config: {exc.errors()}',
            )

    def render(
        self,
        template:    DocumentTemplateSchema,
        data:        dict[str, Any],
        system_vars: dict[str, Any],
    ) -> tuple[bytes, str]:
        try:
            cfg = PdfFormatConfig.model_validate(template.format_configs.get('PDF', {}))
        except ValidationError as exc:
            raise AppException(
                AppErrorCode.DOC_FORMAT_CONFIG_INVALID,
                override_detail=f'PDF config malformed at render time: {exc.errors()}',
            )

        body   = self._engine.interpolate(template.html_template, data, system_vars)
        header = self._engine.interpolate(cfg.header_html, data, system_vars) if cfg.header_html else ''
        footer = self._engine.interpolate(cfg.footer_html, data, system_vars) if cfg.footer_html else ''

        html = (
            '<!doctype html><html><head><meta charset="utf-8"></head><body>'
            f'{header}{body}{footer}'
            '</body></html>'
        )

        page_format = _PAGE_FORMATS.get(cfg.page_size.lower(), 'Letter')
        margin      = f'{cfg.margin_mm}mm'

        pdf = self._converter.to_pdf(html, page_format=page_format, margin=margin)

        return pdf, FORMAT_CONTENT_TYPES[DocumentFormat.PDF]
