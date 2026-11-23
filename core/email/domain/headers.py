"""Strangler shim — implementation lives in ``necore.email.domain.headers``."""
from necore.email.domain.headers import *  # noqa: F401,F403
try:
    from necore.email.domain.headers import __all__  # noqa: F401
except ImportError:
    pass
