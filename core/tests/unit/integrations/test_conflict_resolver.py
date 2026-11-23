"""Matriz escenarios 7–8 — ConflictResolver."""

import pytest

from core.integrations import ConflictResolver


@pytest.mark.unit
class TestConflictResolver:

    def test_wms_wins_on_divergent_status(self):
        merged, warnings = ConflictResolver().apply_wms_wins(
            {'status': 'SHIPPED', 'reference': 'ERP-1'},
            {'status': 'PICKING', 'reference': 'ERP-1'},
            critical_fields=['status'],
        )
        assert merged['status'] == 'PICKING'
        assert len(warnings) == 1

    def test_inbound_new_fields_accepted_without_warning(self):
        merged, warnings = ConflictResolver().apply_wms_wins(
            {'status': 'DRAFT', 'reference': 'NEW-1'},
            {},
            critical_fields=['status'],
        )
        assert merged['status'] == 'DRAFT'
        assert merged['reference'] == 'NEW-1'
        assert warnings == []
