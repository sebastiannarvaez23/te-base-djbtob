"""Strangler shim — implementation lives in ``necore.validators``."""
from necore.validators import *  # noqa: F401,F403
try:
    from necore.validators import __all__  # noqa: F401
except ImportError:
    pass
