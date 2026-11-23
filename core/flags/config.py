"""Factory del store de release flags (base host adapter)."""
from __future__ import annotations

from django.conf import settings

from necore.flags.domain.interfaces import IFlagStore
from necore.flags.infrastructure.fake_store import FakeFlagStore


def _provider_name(override: str | None = None) -> str:
    return (override or getattr(settings, 'FLAG_STORE', 'django')).lower()


def get_flag_store(provider: str | None = None) -> IFlagStore:
    name = _provider_name(provider)
    if name == 'django':
        from platform.features.release.feature_flag.feature_flag.infrastructure.flag_store import (
            CachedDjangoFlagStore,
        )
        return CachedDjangoFlagStore()
    return FakeFlagStore()
