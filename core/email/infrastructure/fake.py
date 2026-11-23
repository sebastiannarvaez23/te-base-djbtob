"""Strangler shim — implementation lives in ``necore.email.infrastructure.fake``."""
from necore.email.infrastructure.fake import *  # noqa: F401,F403
try:
    from necore.email.infrastructure.fake import __all__  # noqa: F401
except ImportError:
    pass
