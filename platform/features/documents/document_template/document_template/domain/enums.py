"""
Enums for the document_template domain.
"""
from enum import Enum


class DocumentFormat(str, Enum):
    """Supported output formats for a document template."""

    HTML = 'HTML'
    PDF  = 'PDF'
    XLSX = 'XLSX'
    CSV  = 'CSV'
    XML  = 'XML'

    @classmethod
    def values(cls) -> list[str]:
        return [m.value for m in cls]


FORMAT_CONTENT_TYPES: dict[DocumentFormat, str] = {
    DocumentFormat.HTML: 'text/html; charset=utf-8',
    DocumentFormat.PDF:  'application/pdf',
    DocumentFormat.XLSX: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    DocumentFormat.CSV:  'text/csv; charset=utf-8',
    DocumentFormat.XML:  'application/xml; charset=utf-8',
}


FORMAT_EXTENSIONS: dict[DocumentFormat, str] = {
    DocumentFormat.HTML: 'html',
    DocumentFormat.PDF:  'pdf',
    DocumentFormat.XLSX: 'xlsx',
    DocumentFormat.CSV:  'csv',
    DocumentFormat.XML:  'xml',
}
