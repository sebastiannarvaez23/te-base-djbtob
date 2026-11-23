"""Strangler shim — implementation lives in ``necore.validators.core``."""
from necore.validators.core import *  # noqa: F401,F403
try:
    from necore.validators.core import __all__  # noqa: F401
except ImportError:
    pass
