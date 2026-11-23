"""Strangler shim — implementation lives in ``necore.decorators.response``."""
from necore.decorators.response import *  # noqa: F401,F403
try:
    from necore.decorators.response import __all__  # noqa: F401
except ImportError:
    pass
