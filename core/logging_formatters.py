"""Strangler shim — implementation lives in ``necore.logging.formatters``."""
from necore.logging.formatters import *  # noqa: F401,F403
try:
    from necore.logging.formatters import __all__  # noqa: F401
except ImportError:
    pass
