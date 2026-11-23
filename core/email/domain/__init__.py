"""Strangler shim — implementation lives in ``necore.email.domain``."""
from necore.email.domain import *  # noqa: F401,F403
try:
    from necore.email.domain import __all__  # noqa: F401
except ImportError:
    pass
