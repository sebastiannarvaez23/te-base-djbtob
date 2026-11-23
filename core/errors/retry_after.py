"""Strangler shim — implementation lives in ``necore.errors.retry_after``."""

from necore.errors.retry_after import (  # noqa: F401
    RETRY_AFTER_HEADER,
    cache_retry_after,
    coerce_retry_after,
)

__all__ = ['RETRY_AFTER_HEADER', 'coerce_retry_after', 'cache_retry_after']
