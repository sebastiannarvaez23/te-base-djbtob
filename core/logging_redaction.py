"""Strangler shim — implementation lives in ``necore.logging.redaction``."""
from necore.logging.redaction import *  # noqa: F401,F403
try:
    from necore.logging.redaction import __all__  # noqa: F401
except ImportError:
    pass
