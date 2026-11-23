"""Strangler shim — implementation lives in ``necore.models``."""
from necore.models import *  # noqa: F401,F403
try:
    from necore.models import __all__  # noqa: F401
except ImportError:
    pass
