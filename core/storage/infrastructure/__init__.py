"""Strangler shim — implementation lives in ``necore.storage.infrastructure``."""
from necore.storage.infrastructure import *  # noqa: F401,F403
try:
    from necore.storage.infrastructure import __all__  # noqa: F401
except ImportError:
    pass
