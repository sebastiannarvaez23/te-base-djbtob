"""Strangler shim — implementation lives in ``necore.email``."""
from necore.email import *  # noqa: F401,F403
try:
    from necore.email import __all__  # noqa: F401
except ImportError:
    pass
