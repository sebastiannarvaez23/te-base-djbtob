"""
Adaptador ``IFlagStore`` respaldado por BD pública + caché Redis.

Lee el snapshot de flags ACTIVE vía ``GetActiveFlagsSnapshotUseCase``
(cacheado e invalidado en cada mutación admin). Cualquier fallo de lectura
devuelve definiciones vacías / ``None`` para que el evaluador caiga en la
lógica antigua.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from core.flags.domain.interfaces import IFlagStore
from core.flags.domain.schemas import FlagDefinition

from ..application.use_cases import GetActiveFlagsSnapshotUseCase
from ..domain.interfaces import IFeatureFlagRepository
from .repositories import DjangoFeatureFlagRepository

logger = logging.getLogger('app.flags')


class CachedDjangoFlagStore(IFlagStore):
    """Store de runtime para release flags (schema público + caché)."""

    def __init__(self, repository: IFeatureFlagRepository | None = None) -> None:
        self._repository = repository or DjangoFeatureFlagRepository()

    def _load_map(self) -> Dict[str, FlagDefinition]:
        try:
            definitions = GetActiveFlagsSnapshotUseCase(self._repository).execute()
            return {flag.key: flag for flag in definitions}
        except Exception:
            logger.warning(
                'Failed to load feature-flag snapshot; defaulting to legacy path',
                exc_info=True,
            )
            return {}

    def get_flag(self, key: str) -> Optional[FlagDefinition]:
        return self._load_map().get(key)

    def list_active_flags(self) -> List[FlagDefinition]:
        return list(self._load_map().values())
