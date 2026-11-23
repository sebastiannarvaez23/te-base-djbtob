"""Unit tests for the small composable blocks: RenderResolver and SystemVarsBuilder.

TemplateLoader hits the ORM, so it's covered by integration tests.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core.errors import AppErrorCode, AppException

from platform.features.documents.document_template.document_template.application.blocks.render_resolver import (
    RenderResolver,
)
from platform.features.documents.document_template.document_template.application.blocks.system_vars_builder import (
    SystemVarsBuilder,
)
from platform.features.documents.document_template.document_template.domain.enums import DocumentFormat


# ── RenderResolver ───────────────────────────────────────────────────────────


def _registry_with(format_to_renderer):
    """Fake registry that returns the given mapping or raises like the real one."""
    registry = MagicMock()
    def _get(fmt):
        if fmt in format_to_renderer:
            return format_to_renderer[fmt]
        raise AppException(
            AppErrorCode.DOC_RENDERER_NOT_REGISTERED,
            override_detail=f'No renderer for {fmt.value}',
        )
    registry.get.side_effect = _get
    return registry


def _template(allowed_formats, format_configs, code='TPL'):
    return SimpleNamespace(
        code=code,
        allowed_formats=allowed_formats,
        format_configs=format_configs,
    )


class TestRenderResolver:

    def test_resolves_when_all_three_align(self):
        renderer = object()
        resolver = RenderResolver(_registry_with({DocumentFormat.PDF: renderer}))
        template = _template(['PDF'], {'PDF': {'page_size': 'letter'}})
        assert resolver.resolve(template, DocumentFormat.PDF) is renderer

    def test_rejects_format_not_in_allowed(self):
        resolver = RenderResolver(_registry_with({}))
        template = _template(['HTML'], {'HTML': {}})

        with pytest.raises(AppException) as exc_info:
            resolver.resolve(template, DocumentFormat.PDF)
        assert exc_info.value.code == AppErrorCode.DOC_FORMAT_NOT_ALLOWED

    def test_rejects_when_format_config_missing(self):
        """allowed_formats says yes but format_configs has no entry."""
        renderer = object()
        resolver = RenderResolver(_registry_with({DocumentFormat.PDF: renderer}))
        template = _template(['PDF'], {})  # config missing

        with pytest.raises(AppException) as exc_info:
            resolver.resolve(template, DocumentFormat.PDF)
        assert exc_info.value.code == AppErrorCode.DOC_FORMAT_CONFIG_MISSING

    def test_rejects_when_renderer_not_registered(self):
        """allowed + config in place, but no renderer wired up for the format."""
        resolver = RenderResolver(_registry_with({}))  # empty registry
        template = _template(['XLSX'], {'XLSX': {'sheet_name': 's'}})

        with pytest.raises(AppException) as exc_info:
            resolver.resolve(template, DocumentFormat.XLSX)
        assert exc_info.value.code == AppErrorCode.DOC_RENDERER_NOT_REGISTERED


# ── SystemVarsBuilder ────────────────────────────────────────────────────────


class TestSystemVarsBuilder:

    def test_always_includes_uuid_and_timestamp(self):
        out = SystemVarsBuilder().build(DocumentFormat.PDF)
        assert 'uuid' in out and len(out['uuid']) > 0
        assert 'timestamp' in out and isinstance(out['timestamp'], int)
        assert 'iso_timestamp' in out

    def test_ext_matches_format(self):
        for fmt, ext in [
            (DocumentFormat.HTML, 'html'),
            (DocumentFormat.PDF,  'pdf'),
            (DocumentFormat.XLSX, 'xlsx'),
            (DocumentFormat.CSV,  'csv'),
            (DocumentFormat.XML,  'xml'),
        ]:
            out = SystemVarsBuilder().build(fmt)
            assert out['ext'] == ext

    def test_year_month_day_zero_padded(self):
        out = SystemVarsBuilder().build(DocumentFormat.PDF)
        assert len(out['year'])  == 4
        assert len(out['month']) == 2
        assert len(out['day'])   == 2

    def test_user_id_propagated(self):
        user = SimpleNamespace(id=42)
        out = SystemVarsBuilder().build(DocumentFormat.PDF, user=user)
        assert out['user_id'] == '42'

    def test_tenant_code_propagated(self):
        tenant = SimpleNamespace(code='acme')
        out = SystemVarsBuilder().build(DocumentFormat.PDF, tenant=tenant)
        assert out['tenant_code'] == 'acme'

    def test_tenant_falls_back_to_schema_name(self):
        tenant = SimpleNamespace(schema_name='acme_schema')
        out = SystemVarsBuilder().build(DocumentFormat.PDF, tenant=tenant)
        assert out['tenant_code'] == 'acme_schema'

    def test_extra_merged_last_and_wins(self):
        """`extra` lets the caller stuff domain-specific vars (invoice_number, etc.)."""
        out = SystemVarsBuilder().build(
            DocumentFormat.PDF,
            extra={'invoice_number': 'INV-001', 'year': 'OVERRIDE'},
        )
        assert out['invoice_number'] == 'INV-001'
        assert out['year'] == 'OVERRIDE'  # extra wins on collision

    def test_no_user_no_tenant_yields_clean_vars(self):
        out = SystemVarsBuilder().build(DocumentFormat.PDF)
        assert 'user_id' not in out
        assert 'tenant_code' not in out
