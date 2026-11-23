"""
XmlDocumentRenderer — emits a tagged XML document from a tabular schema.

Shape:
    <{root_element}>
      <{row_element}>
        <{column.xml_tag or column.key}>value</...>
        ...
      </{row_element}>
      ...
    </{root_element}>

Each column may override its tag name via `xml_tag`. If omitted, the
column key is used. lxml is used so we get proper XML 1.0 escaping and
a pretty-printed output for human readability.
"""
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from core.errors import AppErrorCode, AppException, ValidationAppException

from ...domain.enums import DocumentFormat, FORMAT_CONTENT_TYPES
from ...domain.format_configs import XmlFormatConfig
from ...domain.renderer import IDocumentRenderer
from ...domain.schemas import DocumentTemplateSchema
from .tabular_extractor import extract_cell, resolve_rows


_XML_NAME_RE = re.compile(r'^[A-Za-z_][\w\-.]*$')


class XmlDocumentRenderer(IDocumentRenderer):

    format = DocumentFormat.XML

    def validate_config(self, config: dict[str, Any]) -> None:
        try:
            parsed = XmlFormatConfig.model_validate(config)
        except ValidationError as exc:
            raise ValidationAppException(
                AppErrorCode.DOC_FORMAT_CONFIG_INVALID,
                override_detail=f'Invalid XML config: {exc.errors()}',
            )

        # XML tag names must follow the XML 1.0 Name production. Reject
        # invalid names early so we never produce broken XML at render time.
        for name, label in [
            (parsed.root_element, 'root_element'),
            (parsed.row_element,  'row_element'),
        ]:
            if not _XML_NAME_RE.match(name):
                raise ValidationAppException(
                    AppErrorCode.DOC_FORMAT_CONFIG_INVALID,
                    override_detail=f'{label} "{name}" is not a valid XML element name.',
                )
        for col in parsed.columns:
            tag = col.xml_tag or col.key
            if not _XML_NAME_RE.match(tag):
                raise ValidationAppException(
                    AppErrorCode.DOC_FORMAT_CONFIG_INVALID,
                    override_detail=f'column xml_tag/key "{tag}" is not a valid XML element name.',
                )

    def render(
        self,
        template:    DocumentTemplateSchema,
        data:        dict[str, Any],
        system_vars: dict[str, Any],
    ) -> tuple[bytes, str]:
        try:
            cfg = XmlFormatConfig.model_validate(template.format_configs.get('XML', {}))
        except ValidationError as exc:
            raise AppException(
                AppErrorCode.DOC_FORMAT_CONFIG_INVALID,
                override_detail=f'XML config malformed at render time: {exc.errors()}',
            )

        try:
            from lxml import etree
        except ImportError as exc:
            raise AppException(
                AppErrorCode.DOC_RENDER_FAILED,
                override_detail=f'lxml not installed: {exc}',
            )

        root = etree.Element(cfg.root_element)

        try:
            rows = resolve_rows(cfg.rows_path, data)
            for row in rows:
                row_el = etree.SubElement(root, cfg.row_element)
                for col in cfg.columns:
                    tag = col.xml_tag or col.key
                    cell_el = etree.SubElement(row_el, tag)
                    cell_el.text = self._serialize(extract_cell(row, col))
        except AppException:
            raise
        except Exception as exc:
            raise AppException(
                AppErrorCode.DOC_RENDER_FAILED,
                override_detail=f'XML row generation failed: {exc.__class__.__name__}: {exc}',
            )

        blob = etree.tostring(
            root,
            xml_declaration=True,
            encoding='utf-8',
            pretty_print=True,
        )
        return blob, FORMAT_CONTENT_TYPES[DocumentFormat.XML]

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
