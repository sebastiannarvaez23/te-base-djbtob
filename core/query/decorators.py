"""Strangler shim — implementation lives in ``necore.query.decorators``."""
from necore.query.decorators import *  # noqa: F401,F403
try:
    from necore.query.decorators import __all__  # noqa: F401
except ImportError:
    pass
