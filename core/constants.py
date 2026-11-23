"""Strangler shim — implementation lives in ``necore.constants``."""
from necore.constants import *  # noqa: F401,F403
try:
    from necore.constants import __all__  # noqa: F401
except ImportError:
    pass
