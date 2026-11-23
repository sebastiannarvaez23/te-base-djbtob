"""Strangler shim — implementation lives in ``necore.importing``."""
from necore.importing import *  # noqa: F401,F403
try:
    from necore.importing import __all__  # noqa: F401
except ImportError:
    pass
