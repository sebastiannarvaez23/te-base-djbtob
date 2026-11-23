from typing import Iterable
from uuid import UUID

from core.access.entity_scope import invalidate_entity_scope
from client.features.security.access.entity_grants.domain.interfaces import IGrantScopeInvalidator
from client.features.security.access.entity_grants.domain.schemas import GrantEntityType


class CacheGrantScopeInvalidator(IGrantScopeInvalidator):

    def invalidate(self, user_ids: Iterable[UUID], entity_type: GrantEntityType) -> None:
        invalidate_entity_scope(user_ids, entity_type)
