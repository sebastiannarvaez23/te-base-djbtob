"""Unit tests for format renderers.

HTML and CSV have no native deps and run everywhere. PDF (Playwright/
Chromium), XLSX (openpyxl) and XML (lxml) tests are gated on the lib being
installable on the dev box.

Each renderer is tested for:
  - validate_config() rejects malformed config
  - render() returns (bytes, content_type) with the right shape
  - render() correctly interpolates / applies the template's config
"""
from types import SimpleNamespace

import pytest

from core.errors import AppErrorCode
from core.errors.exceptions import ValidationAppException

from platform.features.documents.document_template.document_template.domain.enums import DocumentFormat
from platform.features.documents.document_template.document_template.infrastructure.jinja_template_engine import (
    JinjaTemplateEngine,
)


def _template(html_template='', format_configs=None):
    return SimpleNamespace(
        html_template=html_template,
        format_configs=format_configs or {},
    )


# ── HTML renderer ────────────────────────────────────────────────────────────


class TestHtmlRenderer:

    def setup_method(self):
        from platform.features.documents.document_template.document_template.infrastructure.renderers.html_renderer import (
            HtmlDocumentRenderer,
        )
        self.renderer = HtmlDocumentRenderer(JinjaTemplateEngine())

    def test_format_attribute(self):
        assert self.renderer.format == DocumentFormat.HTML

    def test_renders_html_template_with_data(self):
        template = _template(
            html_template='<h1>{{ name }}</h1>',
            format_configs={'HTML': {'css_overrides': ''}},
        )
        blob, content_type = self.renderer.render(template, {'name': 'Ana'}, {})
        assert b'<h1>Ana</h1>' in blob
        assert content_type.startswith('text/html')

    def test_css_overrides_injected_when_present(self):
        template = _template(
            html_template='<p>body</p>',
            format_configs={'HTML': {'css_overrides': 'p { color: red; }'}},
        )
        blob, _ = self.renderer.render(template, {}, {})
        text = blob.decode('utf-8')
        assert '<style>p { color: red; }</style>' in text
        assert '<body><p>body</p></body>' in text

    def test_no_css_overrides_yields_bare_body(self):
        template = _template(
            html_template='<p>raw</p>',
            format_configs={'HTML': {'css_overrides': ''}},
        )
        blob, _ = self.renderer.render(template, {}, {})
        assert blob == b'<p>raw</p>'

    def test_validate_config_rejects_unknown_fields(self):
        with pytest.raises(ValidationAppException) as exc_info:
            self.renderer.validate_config({'unknown_field': 'oops'})
        assert exc_info.value.code == AppErrorCode.DOC_FORMAT_CONFIG_INVALID

    def test_system_vars_available_in_template(self):
        template = _template(
            html_template='id={{ uuid }}',
            format_configs={'HTML': {}},
        )
        blob, _ = self.renderer.render(template, {}, {'uuid': 'abc-123'})
        assert b'id=abc-123' in blob


# ── CSV renderer ─────────────────────────────────────────────────────────────


class TestCsvRenderer:

    def setup_method(self):
        from platform.features.documents.document_template.document_template.infrastructure.renderers.csv_renderer import (
            CsvDocumentRenderer,
        )
        self.renderer = CsvDocumentRenderer()

    def test_format_attribute(self):
        assert self.renderer.format == DocumentFormat.CSV

    def test_validate_config_rejects_missing_columns(self):
        with pytest.raises(ValidationAppException) as exc_info:
            self.renderer.validate_config({'rows_path': '$.items'})  # columns missing
        assert exc_info.value.code == AppErrorCode.DOC_FORMAT_CONFIG_INVALID

    def test_validate_config_rejects_extra_fields(self):
        with pytest.raises(ValidationAppException):
            self.renderer.validate_config({
                'rows_path': '$.items',
                'columns':   [{'key': 'a'}],
                'rogue':     True,
            })

    def test_render_emits_header_and_rows(self):
        pytest.importorskip('jsonpath_ng')

        template = _template(format_configs={
            'CSV': {
                'rows_path': '$.items',
                'delimiter': ',',
                'encoding':  'utf-8',
                'columns': [
                    {'key': 'name', 'label': 'Name'},
                    {'key': 'qty',  'label': 'Qty',  'format': 'number'},
                ],
            },
        })
        data = {'items': [{'name': 'A', 'qty': 3}, {'name': 'B', 'qty': 7}]}

        blob, content_type = self.renderer.render(template, data, {})
        text = blob.decode('utf-8')
        assert content_type.startswith('text/csv')
        # Excel-compatible line terminator
        assert '\r\n' in text
        assert 'Name,Qty\r\n' in text
        assert 'A,3\r\n' in text
        assert 'B,7\r\n' in text

    def test_render_unknown_encoding_rejected(self):
        pytest.importorskip('jsonpath_ng')

        template = _template(format_configs={
            'CSV': {
                'rows_path': '$.items',
                'encoding':  'not-a-real-encoding',
                'columns': [{'key': 'a'}],
            },
        })
        from core.errors import AppException
        with pytest.raises(AppException):
            self.renderer.render(template, {'items': [{'a': 1}]}, {})


# ── PDF / XLSX / XML — gated by optional native deps ─────────────────────────


class _FakePdfConverter:
    """Captures the HTML + options the renderer hands off, returns canned
    bytes. Lets us unit-test render() without launching Chromium."""

    def __init__(self, result: bytes = b'%PDF-FAKE'):
        self.result = result
        self.calls: list[dict] = []

    def to_pdf(self, html: str, *, page_format: str, margin: str) -> bytes:
        self.calls.append({'html': html, 'page_format': page_format, 'margin': margin})
        return self.result


class TestPdfRenderer:
    """Document-assembly + config-mapping logic, fully isolated from the
    PDF engine via a fake IPdfConverter. The real Playwright/Chromium path
    is exercised separately in integration tests."""

    def _make(self, converter=None):
        from platform.features.documents.document_template.document_template.infrastructure.renderers.pdf_renderer import (
            PdfDocumentRenderer,
        )
        converter = converter or _FakePdfConverter()
        return PdfDocumentRenderer(JinjaTemplateEngine(), converter), converter

    def test_format_attribute(self):
        renderer, _ = self._make()
        assert renderer.format == DocumentFormat.PDF

    def test_validate_config_rejects_bad_margin_type(self):
        renderer, _ = self._make()
        with pytest.raises(ValidationAppException):
            renderer.validate_config({'margin_mm': 'BIG', 'page_size': 'letter'})

    def test_returns_converter_bytes_and_pdf_content_type(self):
        renderer, _ = self._make(_FakePdfConverter(result=b'%PDF-1.7 xyz'))
        template = _template(html_template='<p>hi</p>', format_configs={'PDF': {}})
        blob, content_type = renderer.render(template, {}, {})
        assert blob == b'%PDF-1.7 xyz'
        assert content_type == 'application/pdf'

    def test_interpolates_data_into_body(self):
        renderer, converter = self._make()
        template = _template(html_template='<h1>{{ name }}</h1>', format_configs={'PDF': {}})
        renderer.render(template, {'name': 'Ana'}, {})
        assert '<h1>Ana</h1>' in converter.calls[0]['html']

    def test_header_body_footer_assembled_in_order(self):
        renderer, converter = self._make()
        template = _template(
            html_template='BODY',
            format_configs={'PDF': {'header_html': 'HEAD', 'footer_html': 'FOOT'}},
        )
        renderer.render(template, {}, {})
        html = converter.calls[0]['html']
        assert html.index('HEAD') < html.index('BODY') < html.index('FOOT')

    def test_no_header_footer_yields_just_body(self):
        renderer, converter = self._make()
        template = _template(html_template='ONLYBODY', format_configs={'PDF': {}})
        renderer.render(template, {}, {})
        html = converter.calls[0]['html']
        assert 'ONLYBODY' in html
        assert '<body>ONLYBODY</body>' in html

    @pytest.mark.parametrize('page_size, expected', [
        ('letter', 'Letter'),
        ('a4',     'A4'),
        ('legal',  'Legal'),
        ('A4',     'A4'),        # case-insensitive
        ('tabloid', 'Letter'),   # unknown → fallback
    ])
    def test_page_size_maps_to_engine_format(self, page_size, expected):
        renderer, converter = self._make()
        template = _template(html_template='x', format_configs={'PDF': {'page_size': page_size}})
        renderer.render(template, {}, {})
        assert converter.calls[0]['page_format'] == expected

    def test_margin_formatted_as_mm(self):
        renderer, converter = self._make()
        template = _template(html_template='x', format_configs={'PDF': {'margin_mm': 25}})
        renderer.render(template, {}, {})
        assert converter.calls[0]['margin'] == '25mm'

    def test_malformed_config_at_render_time_raises(self):
        from core.errors import AppException
        renderer, converter = self._make()
        template = _template(html_template='x', format_configs={'PDF': {'margin_mm': 'BIG'}})
        with pytest.raises(AppException) as exc_info:
            renderer.render(template, {}, {})
        assert exc_info.value.code == AppErrorCode.DOC_FORMAT_CONFIG_INVALID
        # The converter must never be reached when the config is invalid.
        assert converter.calls == []

    def test_converter_failures_propagate(self):
        from core.errors import AppException

        class _BoomConverter:
            def to_pdf(self, html, *, page_format, margin):
                raise AppException(AppErrorCode.DOC_RENDER_FAILED, override_detail='boom')

        renderer, _ = self._make(_BoomConverter())
        template = _template(html_template='x', format_configs={'PDF': {}})
        with pytest.raises(AppException) as exc_info:
            renderer.render(template, {}, {})
        assert exc_info.value.code == AppErrorCode.DOC_RENDER_FAILED


class TestXlsxRendererValidation:

    def setup_method(self):
        from platform.features.documents.document_template.document_template.infrastructure.renderers.xlsx_renderer import (
            XlsxDocumentRenderer,
        )
        self.renderer = XlsxDocumentRenderer()

    def test_format_attribute(self):
        assert self.renderer.format == DocumentFormat.XLSX

    def test_validate_config_requires_sheet_name(self):
        with pytest.raises(ValidationAppException):
            self.renderer.validate_config({'rows_path': '$.x', 'columns': []})


class TestXmlRendererValidation:

    def setup_method(self):
        from platform.features.documents.document_template.document_template.infrastructure.renderers.xml_renderer import (
            XmlDocumentRenderer,
        )
        self.renderer = XmlDocumentRenderer()

    def test_format_attribute(self):
        assert self.renderer.format == DocumentFormat.XML

    def test_invalid_root_element_name_rejected(self):
        with pytest.raises(ValidationAppException) as exc_info:
            self.renderer.validate_config({
                'root_element': '1bad-name',  # XML Names cannot start with a digit
                'row_element':  'item',
                'rows_path':    '$.items',
                'columns':      [{'key': 'x'}],
            })
        assert exc_info.value.code == AppErrorCode.DOC_FORMAT_CONFIG_INVALID

    def test_invalid_xml_tag_rejected(self):
        with pytest.raises(ValidationAppException):
            self.renderer.validate_config({
                'root_element': 'root',
                'row_element':  'item',
                'rows_path':    '$.items',
                'columns':      [{'key': 'x', 'xml_tag': 'bad tag with spaces'}],
            })
