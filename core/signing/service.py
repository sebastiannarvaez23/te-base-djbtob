"""Strangler shim — implementation lives in ``necore.signing.service``."""
from necore.signing.service import *  # noqa: F401,F403
try:
    from necore.signing.service import __all__  # noqa: F401
except ImportError:
    pass
