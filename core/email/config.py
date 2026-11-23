"""Strangler shim — implementation lives in ``necore.email.config``."""
from necore.email.config import *  # noqa: F401,F403
try:
    from necore.email.config import __all__  # noqa: F401
except ImportError:
    pass
