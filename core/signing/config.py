"""Strangler shim — implementation lives in ``necore.signing.config``."""
from necore.signing.config import *  # noqa: F401,F403
try:
    from necore.signing.config import __all__  # noqa: F401
except ImportError:
    pass
