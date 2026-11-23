"""Strangler shim — implementation lives in ``necore.query.patterns``."""
from necore.query.patterns import *  # noqa: F401,F403
try:
    from necore.query.patterns import __all__  # noqa: F401
except ImportError:
    pass
