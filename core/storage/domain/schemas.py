"""Strangler shim — implementation lives in ``necore.storage.domain.schemas``."""
from necore.storage.domain.schemas import *  # noqa: F401,F403
try:
    from necore.storage.domain.schemas import __all__  # noqa: F401
except ImportError:
    pass
