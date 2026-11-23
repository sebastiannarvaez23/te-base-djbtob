"""Strangler shim — implementation lives in ``necore.models.soft_delete``."""
from necore.models.soft_delete import *  # noqa: F401,F403
try:
    from necore.models.soft_delete import __all__  # noqa: F401
except ImportError:
    pass
