"""Strangler shim — implementation lives in ``necore.db_health``."""
from necore.db_health import *  # noqa: F401,F403
try:
    from necore.db_health import __all__  # noqa: F401
except ImportError:
    pass
