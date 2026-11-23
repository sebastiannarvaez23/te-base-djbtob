"""Unit tests for JinjaTemplateEngine.

Cover three concerns:
  1. Basic interpolation contract (variables, conditionals, loops).
  2. System vars are mixed into the context.
  3. Sandbox prevents attribute escape / dangerous globals.

The engine has no Django coupling, so these tests run without DB.
"""
import pytest

from core.errors import AppErrorCode, AppException

from platform.features.documents.document_template.document_template.infrastructure.jinja_template_engine import (
    JinjaTemplateEngine,
)


@pytest.fixture
def engine():
    return JinjaTemplateEngine()


# ── Basic interpolation ───────────────────────────────────────────────────────


class TestBasicInterpolation:

    def test_simple_variable(self, engine):
        result = engine.interpolate('Hello {{ name }}', {'name': 'Ana'})
        assert result == 'Hello Ana'

    def test_missing_variable_renders_empty(self, engine):
        """Default Undefined renders missing vars as empty string (Jinja default)."""
        result = engine.interpolate('Hello {{ missing }}', {})
        assert result == 'Hello '

    def test_if_truthy_branch(self, engine):
        out = engine.interpolate('{% if x %}YES{% endif %}', {'x': True})
        assert out == 'YES'

    def test_if_falsy_branch_omits(self, engine):
        out = engine.interpolate('{% if x %}YES{% endif %}', {'x': False})
        assert out == ''

    def test_for_loop(self, engine):
        out = engine.interpolate(
            '{% for item in items %}{{ item }};{% endfor %}',
            {'items': ['a', 'b', 'c']},
        )
        assert out == 'a;b;c;'

    def test_nested_dict_access(self, engine):
        out = engine.interpolate(
            '{{ user.name }} ({{ user.role }})',
            {'user': {'name': 'Sebas', 'role': 'admin'}},
        )
        assert out == 'Sebas (admin)'


# ── System vars merging ───────────────────────────────────────────────────────


class TestSystemVars:

    def test_system_vars_available_in_context(self, engine):
        out = engine.interpolate(
            'id={{ uuid }}',
            data={},
            system_vars={'uuid': 'abc-123'},
        )
        assert out == 'id=abc-123'

    def test_data_overrides_system_vars(self, engine):
        """User data should win on key collision so admins can override."""
        out = engine.interpolate(
            '{{ kind }}',
            data={'kind': 'CUSTOM'},
            system_vars={'kind': 'DEFAULT'},
        )
        assert out == 'CUSTOM'


# ── Sandbox security ──────────────────────────────────────────────────────────


class TestSandboxSecurity:

    def test_blocks_mro_traversal(self, engine):
        """No way to walk up the type hierarchy to reach object subclasses."""
        with pytest.raises(AppException):
            engine.interpolate('{{ x.__class__.__mro__ }}', {'x': 'abc'})

    def test_blocks_subclasses_global(self, engine):
        """{{ ().__class__.__bases__[0].__subclasses__() }} must fail."""
        evil = '{{ ().__class__.__bases__[0].__subclasses__() }}'
        with pytest.raises(AppException):
            engine.interpolate(evil, {})

    def test_no_import_function(self, engine):
        """__import__ should not be reachable."""
        with pytest.raises(AppException):
            engine.interpolate("{{ __import__('os').system('echo') }}", {})


# ── Error wrapping ────────────────────────────────────────────────────────────


class TestErrorWrapping:

    def test_syntax_error_becomes_app_exception(self, engine):
        with pytest.raises(AppException) as exc_info:
            engine.interpolate('{% if %}', {})
        assert exc_info.value.code == AppErrorCode.DOC_RENDER_FAILED
        assert 'Template interpolation failed' in exc_info.value.detail
