"""Strangler shim — implementation lives in ``necore.signing.domain``."""
from necore.signing.domain import *  # noqa: F401,F403
try:
    from necore.signing.domain import __all__  # noqa: F401
except ImportError:
    pass
