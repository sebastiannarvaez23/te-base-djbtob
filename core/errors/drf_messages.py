"""Strangler shim — implementation lives in ``necore.errors.drf_messages``."""

from necore.errors.drf_messages import (  # noqa: F401
    DRF_VALIDATION_EN,
    english_drf_detail,
    english_str,
    flatten_drf_errors,
)

__all__ = [
    'DRF_VALIDATION_EN',
    'english_str',
    'english_drf_detail',
    'flatten_drf_errors',
]
