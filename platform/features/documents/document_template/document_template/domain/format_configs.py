"""
Per-format configuration schemas.

Each schema validates its own slice of `DocumentTemplate.format_configs`.
A renderer reads only its own schema, never another format's.
"""
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


# ── HTML ──────────────────────────────────────────────────────────────

class HtmlFormatConfig(BaseModel):
    """Extra config for HTML format (the base html_template lives on the model)."""
    model_config = ConfigDict(extra='forbid')

    css_overrides: str = ''


# ── PDF ───────────────────────────────────────────────────────────────

class PdfFormatConfig(BaseModel):
    """PDF rendering options (page setup, headers, footers)."""
    model_config = ConfigDict(extra='forbid')

    page_size:   str  = 'letter'        # letter | A4 | legal
    margin_mm:   int  = Field(default=16, ge=0, le=80)
    header_html: str  = ''
    footer_html: str  = ''


# ── Tabular column (shared by XLSX / CSV / XML) ───────────────────────

class TabularColumn(BaseModel):
    """One column in a tabular export."""
    model_config = ConfigDict(extra='forbid')

    key:     str
    label:   str  = ''
    format:  str  = 'text'              # text | number | date | currency
    xml_tag: Optional[str] = None       # used only by XML; ignored otherwise


# ── XLSX ──────────────────────────────────────────────────────────────

class XlsxHeaderStyle(BaseModel):
    model_config = ConfigDict(extra='forbid')

    bold:       bool = True
    bg_color:   str  = '#1F4E78'
    font_color: str  = '#FFFFFF'


class XlsxFormatConfig(BaseModel):
    """XLSX rendering options. Requires a tabular shape (rows × columns)."""
    model_config = ConfigDict(extra='forbid')

    sheet_name:   str
    rows_path:    str                       # JSONPath, e.g. "$.items"
    columns:      list[TabularColumn]
    header_style: XlsxHeaderStyle = XlsxHeaderStyle()


# ── CSV ───────────────────────────────────────────────────────────────

class CsvFormatConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')

    delimiter: str  = ','
    encoding:  str  = 'utf-8-sig'       # BOM by default for Excel compatibility
    rows_path: str
    columns:   list[TabularColumn]


# ── XML ───────────────────────────────────────────────────────────────

class XmlFormatConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')

    root_element: str
    row_element:  str
    rows_path:    str
    columns:      list[TabularColumn]
