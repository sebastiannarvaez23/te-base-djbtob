"""Strangler shim — implementation lives in ``necore.location``."""
from necore.location import *  # noqa: F401,F403
try:
    from necore.location import __all__  # noqa: F401
except ImportError:
    pass
