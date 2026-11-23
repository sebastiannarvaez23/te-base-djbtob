"""Strangler shim — implementation lives in ``necore.email.application.fallback``."""
from necore.email.application.fallback import *  # noqa: F401,F403
try:
    from necore.email.application.fallback import __all__  # noqa: F401
except ImportError:
    pass
