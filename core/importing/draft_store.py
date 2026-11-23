"""Strangler shim — implementation lives in ``necore.importing.draft_store``."""
from necore.importing.draft_store import *  # noqa: F401,F403
try:
    from necore.importing.draft_store import __all__  # noqa: F401
except ImportError:
    pass
