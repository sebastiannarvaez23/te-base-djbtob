"""Strangler shim — implementation lives in ``necore.signing.domain.schemas``."""
from necore.signing.domain.schemas import *  # noqa: F401,F403
try:
    from necore.signing.domain.schemas import __all__  # noqa: F401
except ImportError:
    pass
