"""Unit tests for the transversal 429 / retry_after contract."""
from __future__ import annotations

import math

import pytest

from core.errors.retry_after import cache_retry_after, coerce_retry_after


pytestmark = pytest.mark.unit


def test_coerce_retry_after_ceils_and_rejects_junk():
    assert coerce_retry_after(1.1) == 2
    assert coerce_retry_after('9') == 9
    assert coerce_retry_after(1) == 1
    assert coerce_retry_after(0.1) == 1
    assert coerce_retry_after(0) is None
    assert coerce_retry_after(-3) is None
    assert coerce_retry_after(True) is None
    assert coerce_retry_after(False) is None
    assert coerce_retry_after(None) is None
    assert coerce_retry_after('') is None
    assert coerce_retry_after('nope') is None
    assert coerce_retry_after(math.inf) is None
    assert coerce_retry_after(math.nan) is None
    assert coerce_retry_after([12]) is None


def test_cache_retry_after_prefers_ttl():
    class _Cache:
        def ttl(self, key):
            assert key == 'k'
            return 4.2

    assert cache_retry_after(_Cache(), 'k') == 5


def test_cache_retry_after_returns_none_when_ttl_is_unusable():
    class _NoTtl:
        pass

    class _TtlMissing:
        def ttl(self, key):
            return -2  # redis: key does not exist

    class _TtlBroken:
        def ttl(self, key):
            raise RuntimeError('cache down')

    assert cache_retry_after(_NoTtl(), 'k') is None
    assert cache_retry_after(_TtlMissing(), 'k') is None
    assert cache_retry_after(_TtlBroken(), 'k') is None
