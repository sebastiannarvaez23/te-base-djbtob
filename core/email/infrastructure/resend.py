"""Strangler shim — implementation lives in ``necore.email.infrastructure.resend``."""
from necore.email.infrastructure.resend import *  # noqa: F401,F403
try:
    from necore.email.infrastructure.resend import __all__  # noqa: F401
except ImportError:
    pass
