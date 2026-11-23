from typing import Iterable, Optional
from uuid import UUID

from django.db import transaction
from django.db.models import Q

from core.access.entity_scope import invalidate_entity_scope
from core.locks import advisory_xact_lock
from client.features.security.access.entity_grants.domain.interfaces import IEntityGrantRepository
from client.features.security.access.entity_grants.domain.schemas import (
    GrantAxis,
    GrantDiff,
    GrantEntityType,
    GrantScope,
    entity_type_key,
)
from client.features.security.access.entity_grants.models import EntityGrant

_LOCK_NAMESPACE = 'entity_grants'

# (columna clave, columna valor) por eje.
_COLUMNS: dict[GrantAxis, tuple[str, str]] = {
    GrantAxis.USER: ('user_id', 'entity_id'),
    GrantAxis.ENTITY: ('entity_id', 'user_id'),
}


def _scope_filter(scope: GrantScope) -> dict:
    key_column, _ = _COLUMNS[scope.axis]
    return {'entity_type': entity_type_key(scope.entity_type), key_column: scope.key_id}


class DjangoEntityGrantRepository(IEntityGrantRepository):

    def list_ids(self, scope: GrantScope) -> set[UUID]:
        _, value_column = _COLUMNS[scope.axis]
        return set(
            EntityGrant.objects.filter(**_scope_filter(scope)).values_list(value_column, flat=True),
        )

    def replace(self, scope: GrantScope, ids: list[UUID], granted_by: Optional[UUID]) -> GrantDiff:
        _, value_column = _COLUMNS[scope.axis]
        base = _scope_filter(scope)
        with transaction.atomic():
            advisory_xact_lock(_LOCK_NAMESPACE, entity_type_key(scope.entity_type))
            current = self.list_ids(scope)
            wanted = set(ids)
            diff = GrantDiff(
                added=sorted(wanted - current, key=str),
                removed=sorted(current - wanted, key=str),
            )
            if diff.removed:
                EntityGrant.objects.filter(**base, **{f'{value_column}__in': diff.removed}).delete()
            if diff.added:
                EntityGrant.objects.bulk_create([
                    EntityGrant(**base, **{value_column: item}, granted_by=granted_by)
                    for item in diff.added
                ])
        return diff

    def granted_keys(self, entity_type: GrantEntityType, axis: GrantAxis) -> set[UUID]:
        key_column, _ = _COLUMNS[axis]
        return set(
            EntityGrant.objects.filter(entity_type=entity_type_key(entity_type))
            .values_list(key_column, flat=True)
            .distinct(),
        )

    def delete_keys(
        self, entity_type: GrantEntityType, user_ids: Iterable[UUID], entity_ids: Iterable[UUID],
    ) -> int:
        users, entities = list(user_ids), list(entity_ids)
        if not users and not entities:
            return 0
        with transaction.atomic():
            advisory_xact_lock(_LOCK_NAMESPACE, entity_type_key(entity_type))
            deleted, _ = EntityGrant.objects.filter(
                Q(user_id__in=users) | Q(entity_id__in=entities),
                entity_type=entity_type_key(entity_type),
            ).delete()
        return deleted


def grant_entity(
    user_id: UUID, entity_type: GrantEntityType, entity_id: UUID, granted_by: Optional[UUID],
) -> None:
    """Writer de ``core.access.entity_scope``: inserta si falta y refresca el alcance al COMMIT."""
    EntityGrant.objects.bulk_create(
        [EntityGrant(user_id=user_id, entity_type=entity_type_key(entity_type), entity_id=entity_id, granted_by=granted_by)],
        ignore_conflicts=True,
    )
    invalidate_entity_scope([user_id], entity_type)


def load_granted_ids(user_id: UUID, entity_type: GrantEntityType) -> set[UUID]:
    """Loader de ``core.access.entity_scope`` (index-only scan sobre el único)."""
    return DjangoEntityGrantRepository().list_ids(
        GrantScope(entity_type=entity_type, axis=GrantAxis.USER, key_id=user_id),
    )
