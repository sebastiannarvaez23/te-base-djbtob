"""Strangler shim — implementation lives in ``necore.validators.data_type``."""
from necore.validators.data_type import *  # noqa: F401,F403
try:
    from necore.validators.data_type import __all__  # noqa: F401
except ImportError:
    pass
