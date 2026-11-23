"""Strangler shim — implementation lives in ``necore.email.domain.interfaces``."""
from necore.email.domain.interfaces import *  # noqa: F401,F403
try:
    from necore.email.domain.interfaces import __all__  # noqa: F401
except ImportError:
    pass
