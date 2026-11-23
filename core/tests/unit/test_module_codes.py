import pytest

from core.module_codes import (
    canonicalize_module_codes,
    filter_codes_in_set_case_insensitive,
    normalize_module_route,
)


@pytest.mark.unit
class TestModuleCodes:

    def test_canonicalize_preserves_catalog_casing(self):
        catalog = {'orders': 'ORDERS', 'settings': 'SETTINGS'}
        assert canonicalize_module_codes(['orders', 'ORDERS', 'settings'], catalog) == [
            'ORDERS', 'SETTINGS',
        ]

    def test_canonicalize_drops_unknown(self):
        catalog = {'orders': 'ORDERS'}
        assert canonicalize_module_codes(['missing', 'orders'], catalog) == ['ORDERS']

    def test_filter_codes_case_insensitive(self):
        codes = ['ORDERS', 'SETTINGS']
        allowed = {'orders', 'picking'}
        assert filter_codes_in_set_case_insensitive(codes, allowed) == ['ORDERS']

    def test_normalize_module_route_adds_leading_slash(self):
        assert normalize_module_route('settings') == '/settings'
        assert normalize_module_route('/orders') == '/orders'
        assert normalize_module_route('') == ''
        assert normalize_module_route(None) == ''
