"""Strangler shim — implementation lives in ``necore.validators.timezone``."""
from necore.validators.timezone import *  # noqa: F401,F403
try:
    from necore.validators.timezone import __all__  # noqa: F401
except ImportError:
    pass
