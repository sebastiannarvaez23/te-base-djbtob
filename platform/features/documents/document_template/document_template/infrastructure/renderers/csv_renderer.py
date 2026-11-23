"""
CsvDocumentRenderer — emits a CSV table from a tabular schema.

Defaults to UTF-8 with BOM so Excel opens it with the correct encoding
out of the box. Delimiter and encoding are configurable per template.
"""
import csv
from datetime import date, datetime
from decimal import Decimal
from io import StringIO
from typing import Any

from pydantic import ValidationError

from core.errors import AppErrorCode, AppException, ValidationAppException

from ...domain.enums import DocumentFormat
from ...domain.format_configs import CsvFormatConfig
from ...domain.renderer import IDocumentRenderer
from ...domain.schemas import DocumentTemplateSchema
from .tabular_extractor import extract_cell, resolve_rows


class CsvDocumentRenderer(IDocumentRenderer):

    format = DocumentFormat.CSV

    def validate_config(self, config: dict[str, Any]) -> None:
        try:
            CsvFormatConfig.model_validate(config)
        except ValidationError as exc:
            raise ValidationAppException(
                AppErrorCode.DOC_FORMAT_CONFIG_INVALID,
                override_detail=f'Invalid CSV config: {exc.errors()}',
            )

    def render(
        self,
        template:    DocumentTemplateSchema,
        data:        dict[str, Any],
        system_vars: dict[str, Any],
    ) -> tuple[bytes, str]:
        try:
            cfg = CsvFormatConfig.model_validate(template.format_configs.get('CSV', {}))
        except ValidationError as exc:
            raise AppException(
                AppErrorCode.DOC_FORMAT_CONFIG_INVALID,
                override_detail=f'CSV config malformed at render time: {exc.errors()}',
            )

        buf = StringIO(newline='')
        writer = csv.writer(buf, delimiter=cfg.delimiter, lineterminator='\r\n')

        writer.writerow([col.label or col.key for col in cfg.columns])

        try:
            rows = resolve_rows(cfg.rows_path, data)
            for row in rows:
                writer.writerow([self._serialize(extract_cell(row, col)) for col in cfg.columns])
        except AppException:
            raise
        except Exception as exc:
            raise AppException(
                AppErrorCode.DOC_RENDER_FAILED,
                override_detail=f'CSV row generation failed: {exc.__class__.__name__}: {exc}',
            )

        try:
            encoded = buf.getvalue().encode(cfg.encoding)
        except LookupError as exc:
            raise AppException(
                AppErrorCode.DOC_FORMAT_CONFIG_INVALID,
                override_detail=f'Unknown CSV encoding "{cfg.encoding}": {exc}',
            )

        content_type = f'text/csv; charset={self._charset_name(cfg.encoding)}'
        return encoded, content_type

    def _serialize(self, value: Any) -> str:
        if value is None:
            return ''
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Decimal):
            return format(value, 'f')
        return str(value)

    def _charset_name(self, encoding: str) -> str:
        # utf-8-sig is just utf-8 with BOM; the wire charset name is utf-8.
        return 'utf-8' if encoding.lower() == 'utf-8-sig' else encoding
