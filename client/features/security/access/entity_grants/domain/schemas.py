from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.access.entity_types import EntityScopeType as GrantEntityType

MAX_GRANTS_PER_REQUEST = 500


def entity_type_key(entity_type) -> str:
    """Valor estable del tipo, sea miembro del enum o texto ya resuelto."""
    value = getattr(entity_type, 'value', None)
    if isinstance(value, str):
        return value
    return str(entity_type)

__all__ = [
    'MAX_GRANTS_PER_REQUEST',
    'GrantAxis',
    'GrantChangeSchema',
    'GrantDiff',
    'GrantEntityType',
    'entity_type_key',
    'GrantScope',
    'GrantSetInput',
    'GrantSetSchema',
    'OrphanPurgeSchema',
]


class GrantAxis(str, Enum):
    """Lado desde el que se administra el conjunto de accesos."""

    USER = 'user'      # clave: usuario · valores: entidades que ve
    ENTITY = 'entity'  # clave: entidad · valores: usuarios que la ven


class GrantScope(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')

    entity_type: str
    axis: GrantAxis
    key_id: UUID


class GrantSetInput(BaseModel):
    """Conjunto completo deseado; vacío revoca todo."""

    model_config = ConfigDict(extra='forbid')

    ids: list[UUID] = Field(default_factory=list, max_length=MAX_GRANTS_PER_REQUEST)

    @field_validator('ids')
    @classmethod
    def _dedupe(cls, value: list[UUID]) -> list[UUID]:
        return list(dict.fromkeys(value))


class GrantDiff(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')

    added: list[UUID] = Field(default_factory=list)
    removed: list[UUID] = Field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.added or self.removed)


class GrantSetSchema(BaseModel):
    model_config = ConfigDict(extra='forbid')

    entity_type: str
    axis: GrantAxis
    key_id: UUID
    ids: list[UUID]


class OrphanPurgeSchema(BaseModel):
    """Accesos cuyo usuario salió de la empresa o cuya entidad ya no existe.

    Los usuarios inactivos siguen siendo de la empresa: sus accesos se conservan.
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    entity_type: str
    missing_users: list[UUID]
    missing_entities: list[UUID]
    deleted: int = 0

    @property
    def found(self) -> bool:
        return bool(self.missing_users or self.missing_entities)


class GrantChangeSchema(GrantSetSchema):
    added: list[UUID]
    removed: list[UUID]

    @property
    def changed(self) -> bool:
        return bool(self.added or self.removed)
