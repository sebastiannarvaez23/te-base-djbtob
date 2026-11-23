"""Strangler shim — implementation lives in ``necore.validators.decorators``."""
from necore.validators.decorators import *  # noqa: F401,F403
try:
    from necore.validators.decorators import __all__  # noqa: F401
except ImportError:
    pass
