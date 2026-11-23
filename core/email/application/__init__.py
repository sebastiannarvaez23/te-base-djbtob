"""Strangler shim — implementation lives in ``necore.email.application``."""
from necore.email.application import *  # noqa: F401,F403
try:
    from necore.email.application import __all__  # noqa: F401
except ImportError:
    pass
