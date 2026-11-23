"""Strangler shim — implementation lives in ``necore.signing``."""
from necore.signing import *  # noqa: F401,F403
try:
    from necore.signing import __all__  # noqa: F401
except ImportError:
    pass
