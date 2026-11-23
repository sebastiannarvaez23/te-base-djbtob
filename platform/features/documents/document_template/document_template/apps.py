from django.apps import AppConfig


class DocumentTemplateAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.documents.document_template.document_template'
    label = 'document_template'
    verbose_name = 'Document templates'

    def ready(self):
        # Wire the renderer registry. Lazy imports to avoid loading
        # heavy deps (Playwright/Chromium, lxml → libxml2) until they're
        # actually needed.
        from .infrastructure.jinja_template_engine import JinjaTemplateEngine
        from .infrastructure.pdf.playwright_pdf_converter import PlaywrightPdfConverter
        from .infrastructure.renderer_registry import RendererRegistry, _set_registry
        from .infrastructure.renderers.csv_renderer import CsvDocumentRenderer
        from .infrastructure.renderers.html_renderer import HtmlDocumentRenderer
        from .infrastructure.renderers.pdf_renderer import PdfDocumentRenderer
        from .infrastructure.renderers.xlsx_renderer import XlsxDocumentRenderer
        from .infrastructure.renderers.xml_renderer import XmlDocumentRenderer

        engine = JinjaTemplateEngine()
        pdf_converter = PlaywrightPdfConverter()
        registry = RendererRegistry()

        # Layout-based (use html_template)
        registry.register(HtmlDocumentRenderer(engine))
        registry.register(PdfDocumentRenderer(engine, pdf_converter))

        # Tabular (use format_configs[X].tabular schema)
        registry.register(XlsxDocumentRenderer())
        registry.register(CsvDocumentRenderer())
        registry.register(XmlDocumentRenderer())

        _set_registry(registry, engine)
