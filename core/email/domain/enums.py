"""Strangler shim — implementation lives in ``necore.email.domain.enums``."""
from necore.email.domain.enums import *  # noqa: F401,F403
try:
    from necore.email.domain.enums import __all__  # noqa: F401
except ImportError:
    pass
