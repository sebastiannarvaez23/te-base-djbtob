"""Strangler shim — implementation lives in ``necore.validators.codes``."""
from necore.validators.codes import *  # noqa: F401,F403
try:
    from necore.validators.codes import __all__  # noqa: F401
except ImportError:
    pass
