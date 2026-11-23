"""Strangler shim — implementation lives in ``necore.models.audit``."""
from necore.models.audit import *  # noqa: F401,F403
try:
    from necore.models.audit import __all__  # noqa: F401
except ImportError:
    pass
