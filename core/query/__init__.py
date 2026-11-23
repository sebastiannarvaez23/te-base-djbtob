"""Strangler shim — implementation lives in ``necore.query``."""
from necore.query import *  # noqa: F401,F403
try:
    from necore.query import __all__  # noqa: F401
except ImportError:
    pass
