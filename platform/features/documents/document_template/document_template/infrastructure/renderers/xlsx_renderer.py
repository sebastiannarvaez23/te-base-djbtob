"""
XlsxDocumentRenderer — produces an XLSX workbook from a tabular schema.

Uses openpyxl's write-only mode so memory stays bounded even with large
result sets: rows are streamed to the workbook one at a time and never
held in a full materialized list.
"""
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any

from pydantic import ValidationError

from core.errors import AppErrorCode, AppException, ValidationAppException

from ...domain.enums import DocumentFormat, FORMAT_CONTENT_TYPES
from ...domain.format_configs import XlsxFormatConfig
from ...domain.renderer import IDocumentRenderer
from ...domain.schemas import DocumentTemplateSchema
from .tabular_extractor import extract_cell, resolve_rows


_NUMBER_FORMATS = {
    'number':   '#,##0.##',
    'currency': '#,##0.00',
    'date':     'yyyy-mm-dd',
}


class XlsxDocumentRenderer(IDocumentRenderer):

    format = DocumentFormat.XLSX

    def validate_config(self, config: dict[str, Any]) -> None:
        try:
            XlsxFormatConfig.model_validate(config)
        except ValidationError as exc:
            raise ValidationAppException(
                AppErrorCode.DOC_FORMAT_CONFIG_INVALID,
                override_detail=f'Invalid XLSX config: {exc.errors()}',
            )

    def render(
        self,
        template:    DocumentTemplateSchema,
        data:        dict[str, Any],
        system_vars: dict[str, Any],
    ) -> tuple[bytes, str]:
        try:
            cfg = XlsxFormatConfig.model_validate(template.format_configs.get('XLSX', {}))
        except ValidationError as exc:
            raise AppException(
                AppErrorCode.DOC_FORMAT_CONFIG_INVALID,
                override_detail=f'XLSX config malformed at render time: {exc.errors()}',
            )

        try:
            from openpyxl import Workbook
            from openpyxl.cell import WriteOnlyCell
            from openpyxl.styles import Font, PatternFill
        except ImportError as exc:
            raise AppException(
                AppErrorCode.DOC_RENDER_FAILED,
                override_detail=f'openpyxl not installed: {exc}',
            )

        wb = Workbook(write_only=True)
        ws = wb.create_sheet(title=cfg.sheet_name[:31])  # Excel sheet title limit

        header_font = Font(
            bold=cfg.header_style.bold,
            color=cfg.header_style.font_color.lstrip('#'),
        )
        header_fill = PatternFill(
            fill_type='solid',
            start_color=cfg.header_style.bg_color.lstrip('#'),
            end_color=cfg.header_style.bg_color.lstrip('#'),
        )

        header_row = []
        for col in cfg.columns:
            cell = WriteOnlyCell(ws, value=col.label or col.key)
            cell.font = header_font
            cell.fill = header_fill
            header_row.append(cell)
        ws.append(header_row)

        try:
            rows = resolve_rows(cfg.rows_path, data)
            for row in rows:
                ws.append([self._to_cell(ws, row, col, WriteOnlyCell) for col in cfg.columns])
        except AppException:
            raise
        except Exception as exc:
            raise AppException(
                AppErrorCode.DOC_RENDER_FAILED,
                override_detail=f'XLSX row generation failed: {exc.__class__.__name__}: {exc}',
            )

        out = BytesIO()
        try:
            wb.save(out)
        except Exception as exc:
            raise AppException(
                AppErrorCode.DOC_RENDER_FAILED,
                override_detail=f'openpyxl failed to write workbook: {exc}',
            )

        return out.getvalue(), FORMAT_CONTENT_TYPES[DocumentFormat.XLSX]

    def _to_cell(self, ws, row: Any, column, WriteOnlyCell):
        value = extract_cell(row, column)
        cell = WriteOnlyCell(ws, value=self._normalize(value))
        fmt = (column.format or 'text').lower()
        if fmt in _NUMBER_FORMATS:
            cell.number_format = _NUMBER_FORMATS[fmt]
        return cell

    def _normalize(self, value: Any):
        """Coerce extractor output to types openpyxl accepts natively."""
        if value is None:
            return ''
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (datetime, date, int, float, str, bool)):
            return value
        return str(value)
