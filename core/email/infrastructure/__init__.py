"""Strangler shim — implementation lives in ``necore.email.infrastructure``."""
from necore.email.infrastructure import *  # noqa: F401,F403
try:
    from necore.email.infrastructure import __all__  # noqa: F401
except ImportError:
    pass
