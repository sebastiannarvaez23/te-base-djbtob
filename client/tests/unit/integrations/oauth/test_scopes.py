"""Unit tests — scope helpers."""

import pytest

from client.features.integrations.oauth.client.domain.scopes import (
    disallowed_scopes,
    normalize_scope_keys,
    parse_scope_string,
)


@pytest.mark.unit
class TestScopes:

    def test_normalize_dedupes_trims_and_sorts(self):
        assert normalize_scope_keys(['api.orders.write', ' api.orders.read ', 'api.orders.read', '']) == [
            'api.orders.read', 'api.orders.write',
        ]

    def test_disallowed_returns_only_unknown_keys(self):
        allowed = {'api.orders.read'}
        assert disallowed_scopes(['api.orders.read'], allowed) == []
        assert disallowed_scopes(['api.orders.read', 'api.hack.all'], allowed) == ['api.hack.all']

    def test_parse_scope_string(self):
        assert parse_scope_string('api.orders.read api.orders.write') == [
            'api.orders.read', 'api.orders.write',
        ]
        assert parse_scope_string(None) == []
        assert parse_scope_string('   ') == []
