from core.validators import Field, RequestBody
from client.features.security.access.entity_grants.domain.schemas import (
    MAX_GRANTS_PER_REQUEST,
    GrantEntityType,
)

ENTITY_TYPES = [item.value for item in GrantEntityType]


class ReplaceGrantSetBody(RequestBody):
    """``ids``: entidades (desde un usuario) o usuarios (desde una entidad)."""

    entity_type = Field(str, choices=ENTITY_TYPES)
    ids = Field(list, item=str, is_uuid=True, max_items=MAX_GRANTS_PER_REQUEST)
