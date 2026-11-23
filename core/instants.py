"""Strangler shim — implementation lives in ``necore.instants``."""
from necore.instants import *  # noqa: F401,F403
try:
    from necore.instants import __all__  # noqa: F401
except ImportError:
    pass
