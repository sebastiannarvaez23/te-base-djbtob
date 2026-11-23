"""Unit tests — category sort key for the functionality catalogs."""
import pytest

from platform.features.security.catalog_order import category_rank


def _ranks(case) -> dict[str, int]:
    return {when.condition.children[0][1]: when.result.value for when in case.cases}


@pytest.mark.unit
def test_orders_features_then_ai_then_api():
    assert _ranks(category_rank()) == {'features': 0, 'ai': 1, 'api': 2}


@pytest.mark.unit
def test_unknown_category_sorts_last():
    assert category_rank().default.value == 3
