"""UUIDv7 generator used as Django PK default."""
from __future__ import annotations

import uuid

import pytest

from core.ids import uuid7


pytestmark = pytest.mark.unit


def test_uuid7_version_and_variant():
    value = uuid7()
    assert value.version == 7
    assert value.variant == uuid.RFC_4122


def test_uuid7_unique():
    seen = {uuid7() for _ in range(500)}
    assert len(seen) == 500


def test_uuid7_monotonic_within_burst():
    values = [uuid7() for _ in range(200)]
    assert values == sorted(values)
