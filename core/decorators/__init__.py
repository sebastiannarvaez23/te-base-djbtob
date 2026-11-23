"""Strangler shim — implementation lives in ``necore.decorators``."""
from necore.decorators import *  # noqa: F401,F403
try:
    from necore.decorators import __all__  # noqa: F401
except ImportError:
    pass
