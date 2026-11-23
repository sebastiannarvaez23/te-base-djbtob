"""Strangler shim — implementation lives in ``necore.errors.handler``."""

from necore.errors.handler import app_exception_handler as _necore_handler

__all__ = ['app_exception_handler']


def app_exception_handler(exc, context):
    """Ensure base sinks are registered even if AppConfig.ready() has not run yet."""
    try:
        from core.apps import ensure_wa_error_sinks
        ensure_wa_error_sinks()
    except Exception:
        pass
    return _necore_handler(exc, context)
