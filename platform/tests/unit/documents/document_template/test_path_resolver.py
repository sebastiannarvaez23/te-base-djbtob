"""Unit tests for PathResolver and extract_static_prefix.

PathResolver is security-critical: it builds an object key that goes
straight to MinIO. These tests exercise the rules that prevent path
traversal, illegal segments, and unresolved-placeholder collisions.
"""
from types import SimpleNamespace

import pytest

from core.errors import AppErrorCode, AppException

from platform.features.documents.document_template.document_template.application.blocks.path_resolver import (
    PathResolver,
    extract_path_variable,
    extract_static_prefix,
)
from platform.features.documents.document_template.document_template.infrastructure.jinja_template_engine import (
    JinjaTemplateEngine,
)


@pytest.fixture
def resolver():
    return PathResolver(JinjaTemplateEngine())


def _template(path: str):
    """Lightweight DocumentTemplate stand-in — only the field we need."""
    return SimpleNamespace(storage_path_template=path)


# ── Happy paths ──────────────────────────────────────────────────────────────


class TestResolveSuccess:

    def test_static_path(self, resolver):
        result = resolver.resolve(_template('facturas/INV-001.pdf'), {}, {})
        assert result == 'facturas/INV-001.pdf'

    def test_interpolated_path(self, resolver):
        result = resolver.resolve(
            _template('facturas/{{ year }}/{{ number }}.pdf'),
            data={'number': '00012'},
            system_vars={'year': '2026'},
        )
        assert result == 'facturas/2026/00012.pdf'

    def test_strips_leading_and_trailing_slashes(self, resolver):
        result = resolver.resolve(_template('/x/y/'), {}, {})
        assert result == 'x/y'

    def test_collapses_empty_segments(self, resolver):
        result = resolver.resolve(_template('a///b'), {}, {})
        assert result == 'a/b'


# ── Failure modes ────────────────────────────────────────────────────────────


class TestResolveFailures:

    def test_empty_template_rejected(self, resolver):
        with pytest.raises(AppException) as exc_info:
            resolver.resolve(_template(''), {}, {})
        assert exc_info.value.code == AppErrorCode.DOC_STORAGE_PATH_INVALID

    def test_unresolved_placeholder_rejected(self, resolver):
        """If the path keeps {{ ... }} after interpolation, collision risk."""
        with pytest.raises(AppException) as exc_info:
            resolver.resolve(_template('facturas/{{ missing }}.pdf'), {}, {})
        assert exc_info.value.code == AppErrorCode.DOC_STORAGE_PATH_INVALID

    def test_traversal_segment_rejected(self, resolver):
        with pytest.raises(AppException) as exc_info:
            resolver.resolve(_template('facturas/../etc/passwd'), {}, {})
        assert exc_info.value.code == AppErrorCode.DOC_STORAGE_PATH_INVALID

    def test_only_dots_rejected(self, resolver):
        with pytest.raises(AppException):
            resolver.resolve(_template('./facturas'), {}, {})

    def test_illegal_chars_get_replaced(self, resolver):
        """Backslashes, colons and similar must be sanitised, not pass through."""
        result = resolver.resolve(_template('a:b/c<d>e.pdf'), {}, {})
        # Each illegal char becomes '_', segments preserved.
        assert ':' not in result and '<' not in result and '>' not in result

    def test_empty_after_sanitization_rejected(self, resolver):
        with pytest.raises(AppException) as exc_info:
            resolver.resolve(_template('///'), {}, {})
        assert exc_info.value.code == AppErrorCode.DOC_STORAGE_PATH_INVALID


# ── extract_static_prefix ────────────────────────────────────────────────────


class TestExtractStaticPrefix:

    def test_prefix_before_first_placeholder(self):
        assert extract_static_prefix('facturas/{{ year }}/x.pdf') == 'facturas/'

    def test_nested_prefix(self):
        assert extract_static_prefix('a/b/c/{{ year }}/x.pdf') == 'a/b/c/'

    def test_no_placeholders_returns_directory_part(self):
        assert extract_static_prefix('a/b/c/file.pdf') == 'a/b/c/'

    def test_placeholder_at_start_returns_empty(self):
        assert extract_static_prefix('{{ kind }}/y/x.pdf') == ''

    def test_empty_input_returns_empty(self):
        assert extract_static_prefix('') == ''

    def test_only_filename_returns_empty(self):
        assert extract_static_prefix('file.pdf') == ''

    def test_leading_slash_stripped(self):
        assert extract_static_prefix('/facturas/{{ year }}/x.pdf') == 'facturas/'

    def test_jinja_block_also_triggers_cutoff(self):
        assert extract_static_prefix('a/b/{% if x %}foo{% endif %}.pdf') == 'a/b/'


# ── extract_path_variable ───────────────────────────────────────────────────


class TestExtractPathVariable:

    def test_reads_tenant_code_segment(self):
        tpl = 'admin/invoicing/{{ year }}/{{ tenant_code }}/INV-{{ uuid }}.pdf'
        key = 'admin/invoicing/2026/acme_corp/INV-001-abc.pdf'
        assert extract_path_variable(tpl, key, 'tenant_code') == 'acme_corp'

    def test_reads_year_segment(self):
        tpl = 'admin/invoicing/{{ year }}/{{ tenant_code }}/file.pdf'
        key = 'admin/invoicing/2026/acme_corp/file.pdf'
        assert extract_path_variable(tpl, key, 'year') == '2026'

    def test_missing_variable_returns_none(self):
        tpl = 'facturas/{{ year }}/file.pdf'
        key = 'facturas/2026/file.pdf'
        assert extract_path_variable(tpl, key, 'tenant_code') is None

    def test_short_object_key_returns_none(self):
        tpl = 'a/{{ tenant_code }}/b.pdf'
        assert extract_path_variable(tpl, 'a/b.pdf', 'tenant_code') is None
