"""Matriz escenario 21 — mapping engine validation."""

import pytest

from core.errors.exceptions import ValidationAppException
from client.features.integrations.connections.profile.application.mapping_engine import apply_mapping, validate_mapping_rules


@pytest.mark.unit
class TestMappingEngine:

    def test_apply_mapping(self):
        rules = [
            {'source': 'OrderID', 'target': 'external_id'},
            {'source': 'Status', 'target': 'status'},
        ]
        result = apply_mapping(rules, {'OrderID': 'ERP-1', 'Status': 'OPEN'})
        assert result == {'external_id': 'ERP-1', 'status': 'OPEN'}

    def test_invalid_rule_raises(self):
        with pytest.raises(ValidationAppException):
            validate_mapping_rules([{'source': 'only'}])

    def test_outbound_mapping(self):
        rules = [{'source': 'external_id', 'target': 'OrderID'}]
        assert apply_mapping(rules, {'external_id': 'W-9'}) == {'OrderID': 'W-9'}
