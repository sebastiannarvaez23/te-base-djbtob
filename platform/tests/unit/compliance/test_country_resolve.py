"""Unit tests for company policy country duck-typed resolve."""

from types import SimpleNamespace

import pytest

from platform.features.compliance.policy.policy.application.country_resolve import (
    resolve_company_policy_country,
)


@pytest.mark.unit
def test_resolve_from_geo_city_graph():
    company = SimpleNamespace(
        geo_city=SimpleNamespace(
            department=SimpleNamespace(
                country=SimpleNamespace(code='co'),
            ),
        ),
    )
    assert resolve_company_policy_country(company) == 'CO'


@pytest.mark.unit
def test_resolve_none_without_geo_city():
    assert resolve_company_policy_country(SimpleNamespace(geo_city=None)) is None
    assert resolve_company_policy_country(None) is None
