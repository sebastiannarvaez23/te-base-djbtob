"""Strangler shim — implementation lives in ``necore.storage``."""
from necore.storage import *  # noqa: F401,F403
try:
    from necore.storage import __all__  # noqa: F401
except ImportError:
    pass
