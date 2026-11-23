"""Unit tests for duck-typed geography labels and codes."""
from types import SimpleNamespace

import pytest

from core.location import entity_location_city_line, entity_location_codes, entity_location_labels

pytestmark = pytest.mark.unit


def _company():
    country = SimpleNamespace(name='Colombia', code='co')
    department = SimpleNamespace(name='Cundinamarca', code='cund', country=country)
    city = SimpleNamespace(name='Bogotá', code='11001', department=department)
    return SimpleNamespace(geo_city=city)


def test_entity_location_labels_from_geo_city():
    assert entity_location_labels(_company()) == ('Colombia', 'Cundinamarca', 'Bogotá')


def test_entity_location_codes_normalized_uppercase():
    assert entity_location_codes(_company()) == ('CO', 'CUND', '11001')


def test_entity_location_city_line():
    assert entity_location_city_line(_company()) == 'Bogotá, Cundinamarca, Colombia'


def test_entity_location_empty_without_geo_city():
    empty = SimpleNamespace(geo_city=None)
    assert entity_location_labels(empty) == ('', '', '')
    assert entity_location_codes(empty) == ('', '', '')
    assert entity_location_city_line(empty) == ''
