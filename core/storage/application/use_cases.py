"""Strangler shim — implementation lives in ``necore.storage.application.use_cases``."""
from necore.storage.application.use_cases import *  # noqa: F401,F403
try:
    from necore.storage.application.use_cases import __all__  # noqa: F401
except ImportError:
    pass
