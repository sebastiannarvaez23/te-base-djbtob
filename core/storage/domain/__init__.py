"""Strangler shim — implementation lives in ``necore.storage.domain``."""
from necore.storage.domain import *  # noqa: F401,F403
try:
    from necore.storage.domain import __all__  # noqa: F401
except ImportError:
    pass
