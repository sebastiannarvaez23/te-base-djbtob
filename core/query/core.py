"""Strangler shim — implementation lives in ``necore.query.core``."""
from necore.query.core import *  # noqa: F401,F403
try:
    from necore.query.core import __all__  # noqa: F401
except ImportError:
    pass
