"""Strangler shim — implementation lives in ``necore.email.infrastructure.smtp``."""
from necore.email.infrastructure.smtp import *  # noqa: F401,F403
try:
    from necore.email.infrastructure.smtp import __all__  # noqa: F401
except ImportError:
    pass
