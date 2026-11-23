"""Unit tests for admin document preview context enrichment."""
from platform.features.documents.document_template.document_template.application.preview_context import (
    enrich_preview_path_context,
)


def test_injects_demo_tenant_when_missing():
    data, sys_vars = enrich_preview_path_context({}, {'year': '2026'})
    assert sys_vars['tenant_code'] == 'demo_tenant'
    assert sys_vars['year'] == '2026'


def test_keeps_explicit_tenant_in_data():
    data, sys_vars = enrich_preview_path_context(
        {'tenant_code': 'acme'},
        {},
    )
    assert 'tenant_code' not in sys_vars
    assert data['tenant_code'] == 'acme'


def test_derives_number_from_invoice_number_stripping_inv_prefix():
    data, _ = enrich_preview_path_context(
        {'invoice_number': 'INV-202606-71EA68EB'},
        {'tenant_code': 'demo_tenant'},
    )
    assert data['number'] == '202606-71EA68EB'


def test_derives_number_without_inv_prefix():
    data, _ = enrich_preview_path_context(
        {'invoice_number': 'FAC-2026-000154'},
        {},
    )
    assert data['number'] == 'FAC-2026-000154'


def test_does_not_override_existing_number():
    data, _ = enrich_preview_path_context(
        {'invoice_number': 'INV-1', 'number': 'custom'},
        {},
    )
    assert data['number'] == 'custom'
