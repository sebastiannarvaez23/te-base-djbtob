"""Strangler shim — implementation lives in ``necore.storage.infrastructure.minio_storage``."""
from necore.storage.infrastructure.minio_storage import *  # noqa: F401,F403
try:
    from necore.storage.infrastructure.minio_storage import __all__  # noqa: F401
except ImportError:
    pass
