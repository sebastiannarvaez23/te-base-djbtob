"""Strangler shim — implementation lives in ``necore.identifiers``."""
from necore.identifiers import *  # noqa: F401,F403
try:
    from necore.identifiers import __all__  # noqa: F401
except ImportError:
    pass
