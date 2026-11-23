"""Backwards-compatible re-export of the pure create-input validator.

The actual rule lives in ``domain.services.create_rules`` (no Django). Kept here
so existing callers/tests that import from the application layer keep working.
"""

from ..domain.services.create_rules import validate_create_input

__all__ = ['validate_create_input']
