"""Strangler shim — implementation lives in ``necore.errors.compose``."""

from necore.errors.compose import compose_error_code, compose_registry  # noqa: F401

__all__ = ['compose_error_code', 'compose_registry']
