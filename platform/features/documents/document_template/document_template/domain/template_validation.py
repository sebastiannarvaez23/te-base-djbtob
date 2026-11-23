"""
Synchronization invariants for a DocumentTemplate.

Rules enforced:
  1. allowed_formats not empty
  2. all values are valid DocumentFormat members
  3. default_format is in allowed_formats
  4. for every format in allowed_formats, format_configs[format] exists
     and validates against its per-format pydantic schema
  5. if is_storable, storage_path_template is non-empty and contains
     {{ uuid }} or {{ timestamp }} (uniqueness token)

Used by both DRF serializers (at the API boundary) and model.clean()
(as a last-line defense for direct ORM writes / admin).
"""
import re
from typing import Any

from pydantic import ValidationError

from core.errors import AppErrorCode, ValidationAppException

from .enums import DocumentFormat
from .format_configs import (
    CsvFormatConfig,
    HtmlFormatConfig,
    PdfFormatConfig,
    XlsxFormatConfig,
    XmlFormatConfig,
)


_FORMAT_CONFIG_SCHEMAS = {
    DocumentFormat.HTML: HtmlFormatConfig,
    DocumentFormat.PDF:  PdfFormatConfig,
    DocumentFormat.XLSX: XlsxFormatConfig,
    DocumentFormat.CSV:  CsvFormatConfig,
    DocumentFormat.XML:  XmlFormatConfig,
}

_UNIQUENESS_TOKEN_RE = re.compile(r'\{\{\s*(uuid|timestamp)\s*\}\}')


def validate_template_sync(
    allowed_formats:       list[str],
    default_format:        str,
    format_configs:        dict[str, Any],
    is_storable:           bool,
    storage_path_template: str,
) -> None:
    """Raise ValidationAppException if any synchronization invariant is broken."""

    if not allowed_formats:
        raise ValidationAppException(
            AppErrorCode.DOC_ALLOWED_FORMATS_EMPTY,
            override_detail='The template must allow at least one format.',
        )

    valid_values = set(DocumentFormat.values())
    invalid = [f for f in allowed_formats if f not in valid_values]
    if invalid:
        raise ValidationAppException(
            AppErrorCode.DOC_FORMAT_CONFIG_INVALID,
            override_detail=f'Unknown formats in allowed_formats: {invalid}. '
                            f'Valid: {sorted(valid_values)}',
        )

    if default_format not in allowed_formats:
        raise ValidationAppException(
            AppErrorCode.DOC_DEFAULT_FORMAT_MISMATCH,
            override_detail=f'default_format "{default_format}" is not in '
                            f'allowed_formats {allowed_formats}',
        )

    for fmt in allowed_formats:
        cfg = format_configs.get(fmt)
        if cfg is None:
            raise ValidationAppException(
                AppErrorCode.DOC_FORMAT_CONFIG_MISSING,
                override_detail=f'Format {fmt} is allowed but has no entry in format_configs.',
            )
        schema_cls = _FORMAT_CONFIG_SCHEMAS[DocumentFormat(fmt)]
        try:
            schema_cls.model_validate(cfg)
        except ValidationError as exc:
            raise ValidationAppException(
                AppErrorCode.DOC_FORMAT_CONFIG_INVALID,
                override_detail=f'Invalid config for format {fmt}: {exc.errors()}',
            )

    if is_storable:
        if not storage_path_template.strip():
            raise ValidationAppException(
                AppErrorCode.DOC_STORAGE_PATH_INVALID,
                override_detail='storage_path_template is required when is_storable=True.',
            )
        if not _UNIQUENESS_TOKEN_RE.search(storage_path_template):
            raise ValidationAppException(
                AppErrorCode.DOC_STORAGE_PATH_INVALID,
                override_detail='storage_path_template must contain {{ uuid }} or {{ timestamp }} '
                                'to guarantee unique object keys.',
            )
