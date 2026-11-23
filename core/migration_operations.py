"""Strangler shim — implementation lives in ``necore.migration_operations``."""
from necore.migration_operations import *  # noqa: F401,F403
try:
    from necore.migration_operations import __all__  # noqa: F401
except ImportError:
    pass
