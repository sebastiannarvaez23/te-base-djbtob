"""Strangler shim — implementation lives in ``necore.storage.application``."""
from necore.storage.application import *  # noqa: F401,F403
try:
    from necore.storage.application import __all__  # noqa: F401
except ImportError:
    pass
