"""Unit tests for the synchronization invariant validator.

The validator enforces the contract: every format in `allowed_formats`
must have a matching, well-formed entry in `format_configs`, the
default_format must be allowed, and storable templates must use a
unique-by-design path.
"""
import pytest

from core.errors import AppErrorCode
from core.errors.exceptions import ValidationAppException

from platform.features.documents.document_template.document_template.domain.template_validation import (
    validate_template_sync,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def html_pdf_configs():
    return {
        'HTML': {'css_overrides': ''},
        'PDF':  {
            'page_size': 'letter',
            'margin_mm': 16,
            'header_html': '',
            'footer_html': '',
        },
    }


@pytest.fixture
def xlsx_config():
    return {
        'sheet_name': 'Detail',
        'rows_path':  '$.items',
        'columns':    [{'key': 'name', 'label': 'Name', 'format': 'text'}],
    }


# ── Happy paths ──────────────────────────────────────────────────────────────


class TestValidConfigurations:

    def test_html_pdf_combo(self, html_pdf_configs):
        validate_template_sync(
            allowed_formats=['HTML', 'PDF'],
            default_format='PDF',
            format_configs=html_pdf_configs,
            is_storable=False,
            storage_path_template='',
        )

    def test_storable_with_uuid_token(self, html_pdf_configs):
        validate_template_sync(
            allowed_formats=['PDF'],
            default_format='PDF',
            format_configs={'PDF': html_pdf_configs['PDF']},
            is_storable=True,
            storage_path_template='facturas/{{ year }}/{{ uuid }}.pdf',
        )

    def test_storable_with_timestamp_token(self, html_pdf_configs):
        validate_template_sync(
            allowed_formats=['PDF'],
            default_format='PDF',
            format_configs={'PDF': html_pdf_configs['PDF']},
            is_storable=True,
            storage_path_template='facturas/{{ timestamp }}.pdf',
        )


# ── Failures: allowed_formats ────────────────────────────────────────────────


class TestAllowedFormatsRules:

    def test_empty_allowed_formats_rejected(self):
        with pytest.raises(ValidationAppException) as exc_info:
            validate_template_sync(
                allowed_formats=[],
                default_format='PDF',
                format_configs={},
                is_storable=False,
                storage_path_template='',
            )
        assert exc_info.value.code == AppErrorCode.DOC_ALLOWED_FORMATS_EMPTY

    def test_unknown_format_rejected(self):
        with pytest.raises(ValidationAppException) as exc_info:
            validate_template_sync(
                allowed_formats=['DOCX'],
                default_format='DOCX',
                format_configs={'DOCX': {}},
                is_storable=False,
                storage_path_template='',
            )
        assert exc_info.value.code == AppErrorCode.DOC_FORMAT_CONFIG_INVALID
        assert 'Unknown formats' in exc_info.value.detail

    def test_default_must_be_in_allowed(self, html_pdf_configs):
        with pytest.raises(ValidationAppException) as exc_info:
            validate_template_sync(
                allowed_formats=['HTML', 'PDF'],
                default_format='XLSX',
                format_configs=html_pdf_configs,
                is_storable=False,
                storage_path_template='',
            )
        assert exc_info.value.code == AppErrorCode.DOC_DEFAULT_FORMAT_MISMATCH


# ── Failures: format_configs synchronization ─────────────────────────────────


class TestFormatConfigSync:

    def test_missing_config_for_allowed_format(self):
        """allowed=[HTML,PDF] but format_configs lacks PDF → reject."""
        with pytest.raises(ValidationAppException) as exc_info:
            validate_template_sync(
                allowed_formats=['HTML', 'PDF'],
                default_format='HTML',
                format_configs={'HTML': {'css_overrides': ''}},  # PDF missing
                is_storable=False,
                storage_path_template='',
            )
        assert exc_info.value.code == AppErrorCode.DOC_FORMAT_CONFIG_MISSING
        assert 'PDF' in exc_info.value.detail

    def test_invalid_config_shape_rejected(self):
        """PDF config without required structure → reject."""
        with pytest.raises(ValidationAppException) as exc_info:
            validate_template_sync(
                allowed_formats=['PDF'],
                default_format='PDF',
                format_configs={'PDF': {'page_size': 'letter', 'margin_mm': 'NOT-A-NUMBER'}},
                is_storable=False,
                storage_path_template='',
            )
        assert exc_info.value.code == AppErrorCode.DOC_FORMAT_CONFIG_INVALID

    def test_xlsx_without_columns_rejected(self):
        """XLSX requires sheet_name + rows_path + columns at minimum."""
        with pytest.raises(ValidationAppException) as exc_info:
            validate_template_sync(
                allowed_formats=['XLSX'],
                default_format='XLSX',
                format_configs={'XLSX': {}},
                is_storable=False,
                storage_path_template='',
            )
        assert exc_info.value.code == AppErrorCode.DOC_FORMAT_CONFIG_INVALID


# ── Failures: storage path ──────────────────────────────────────────────────


class TestStoragePathRules:

    def test_storable_requires_path(self, html_pdf_configs):
        with pytest.raises(ValidationAppException) as exc_info:
            validate_template_sync(
                allowed_formats=['PDF'],
                default_format='PDF',
                format_configs={'PDF': html_pdf_configs['PDF']},
                is_storable=True,
                storage_path_template='',
            )
        assert exc_info.value.code == AppErrorCode.DOC_STORAGE_PATH_INVALID
        assert 'required' in exc_info.value.detail

    def test_storable_path_must_have_uniqueness_token(self, html_pdf_configs):
        """A path without {{ uuid }} or {{ timestamp }} would collide."""
        with pytest.raises(ValidationAppException) as exc_info:
            validate_template_sync(
                allowed_formats=['PDF'],
                default_format='PDF',
                format_configs={'PDF': html_pdf_configs['PDF']},
                is_storable=True,
                storage_path_template='facturas/{{ year }}/INV-{{ number }}.pdf',
            )
        assert exc_info.value.code == AppErrorCode.DOC_STORAGE_PATH_INVALID
        assert 'uniqueness' in exc_info.value.detail.lower() or 'uuid' in exc_info.value.detail

    def test_non_storable_does_not_require_path(self, html_pdf_configs):
        """If is_storable=False, the path can be empty without issue."""
        validate_template_sync(
            allowed_formats=['PDF'],
            default_format='PDF',
            format_configs={'PDF': html_pdf_configs['PDF']},
            is_storable=False,
            storage_path_template='',
        )
