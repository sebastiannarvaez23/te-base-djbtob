"""Strangler shim — implementation lives in ``necore.email.domain.schemas``."""
from necore.email.domain.schemas import *  # noqa: F401,F403
try:
    from necore.email.domain.schemas import __all__  # noqa: F401
except ImportError:
    pass
