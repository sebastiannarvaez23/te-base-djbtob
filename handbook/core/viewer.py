"""Lector del handbook: anónimo, admin de plataforma o usuario de tenant."""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Literal, Optional

ViewerKind = Literal['anonymous', 'admin', 'client']


@dataclass(frozen=True)
class HandbookViewer:
    kind: ViewerKind
    user_id: Optional[str] = None
    is_superuser: bool = False
    features: FrozenSet[str] = frozenset()
    schema_name: Optional[str] = None

    @classmethod
    def anonymous(cls) -> 'HandbookViewer':
        return cls(kind='anonymous')

    @classmethod
    def admin(
        cls,
        *,
        user_id: str,
        features: FrozenSet[str],
        is_superuser: bool = False,
    ) -> 'HandbookViewer':
        return cls(
            kind='admin',
            user_id=user_id,
            is_superuser=is_superuser,
            features=features,
            schema_name='public',
        )

    @classmethod
    def client(
        cls,
        *,
        user_id: str,
        features: FrozenSet[str],
        schema_name: str,
    ) -> 'HandbookViewer':
        return cls(
            kind='client',
            user_id=user_id,
            features=features,
            schema_name=schema_name,
        )

    def has(self, feature_key: Optional[str]) -> bool:
        if not feature_key:
            return True
        if self.kind == 'admin' and self.is_superuser:
            return True
        return feature_key in self.features
