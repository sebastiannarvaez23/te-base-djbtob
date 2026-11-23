"""Strangler shim — implementation lives in ``necore.logging.filters``."""
from necore.logging.filters import *  # noqa: F401,F403
try:
    from necore.logging.filters import __all__  # noqa: F401
except ImportError:
    pass
