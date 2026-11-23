"""Strangler shim — implementation lives in ``necore.ids``."""
from necore.ids import *  # noqa: F401,F403
try:
    from necore.ids import __all__  # noqa: F401
except ImportError:
    pass
