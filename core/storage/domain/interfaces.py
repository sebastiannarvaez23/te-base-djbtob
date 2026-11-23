"""Strangler shim — implementation lives in ``necore.storage.domain.interfaces``."""
from necore.storage.domain.interfaces import *  # noqa: F401,F403
try:
    from necore.storage.domain.interfaces import __all__  # noqa: F401
except ImportError:
    pass
