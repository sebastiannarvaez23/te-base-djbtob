"""Strangler shim — implementation lives in ``necore.importing.file_parsers``."""
from necore.importing.file_parsers import *  # noqa: F401,F403
try:
    from necore.importing.file_parsers import __all__  # noqa: F401
except ImportError:
    pass
