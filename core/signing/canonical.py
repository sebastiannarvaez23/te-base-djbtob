"""Strangler shim — implementation lives in ``necore.signing.canonical``."""
from necore.signing.canonical import *  # noqa: F401,F403
try:
    from necore.signing.canonical import __all__  # noqa: F401
except ImportError:
    pass
