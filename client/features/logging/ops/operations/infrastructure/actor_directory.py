"""Adaptador: UUID de usuario → nombre visible en la trazabilidad."""
from uuid import UUID

from django.contrib.auth import get_user_model

from client.features.logging.ops.operations.domain.interfaces import IActorDirectory


class DjangoActorDirectory(IActorDirectory):

    def display_names(self, user_ids: set[UUID]) -> dict[UUID, str]:
        if not user_ids:
            return {}
        rows = get_user_model().objects.filter(pk__in=user_ids).only(
            'id', 'username', 'first_name', 'last_name',
        )
        return {user.id: _display_name(user) for user in rows}


def _display_name(user) -> str:
    full_name = f'{user.first_name or ""} {user.last_name or ""}'.strip()
    return full_name or (user.username or '').strip()
