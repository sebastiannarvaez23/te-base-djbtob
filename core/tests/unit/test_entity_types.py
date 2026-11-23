"""El enum de tipos de entidad es puro y el mismo que expone ``entity_scope``."""
import pytest

from core.access import entity_scope, entity_types

pytestmark = pytest.mark.unit


def test_entity_scope_reexports_the_pure_enum():
    assert entity_scope.EntityScopeType is entity_types.EntityScopeType


def test_product_entity_types_start_empty():
    assert list(entity_types.EntityScopeType) == []
