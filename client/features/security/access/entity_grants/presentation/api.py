from uuid import UUID

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.permissions import HasSubscriptionAccess, IsCompanyAdmin, IsCompanyMember
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from client.features.security.access.entity_grants.domain.schemas import (
    GrantAxis,
    GrantScope,
    GrantSetInput,
)
from client.features.security.access.entity_grants.presentation import dependencies as deps
from client.features.security.access.entity_grants.presentation.bodies import ReplaceGrantSetBody
from client.features.security.access.entity_grants.presentation.queries import GrantSetQuery

_AUDIT_ENTITY = 'EntityGrant'
_AUDIT_FIELDS = {'entity_type', 'axis', 'added', 'removed'}


class _GrantSetView(APIView):
    """GET/PUT del conjunto de accesos visto desde ``axis``."""

    permission_classes = [IsAuthenticated, IsCompanyAdmin]
    axis: GrantAxis

    def _scope(self, entity_type: str, key_id: UUID) -> GrantScope:
        return GrantScope(entity_type=entity_type, axis=self.axis, key_id=key_id)

    @validated_query(GrantSetQuery)
    def get(self, request, key_id: UUID, *, query: PaginatedQuery):
        scope = self._scope(query.filters['entity_type'], key_id)
        result = deps.get_grant_set(scope.entity_type).execute(request.user.company_id, scope)
        return wrap_response(result.model_dump(mode='json'), message='OK')

    @validated_body(ReplaceGrantSetBody)
    def put(self, request, key_id: UUID, *, body: dict):
        scope = self._scope(body['entity_type'], key_id)
        result = deps.replace_grant_set(scope.entity_type).execute(
            request.user.company_id, scope, GrantSetInput(ids=body['ids']), request.user.id,
        )
        if result.changed:
            audit_log(
                request, _AUDIT_ENTITY, key_id, 'UPDATE',
                f'Access grants updated from {self.axis.value}',
                changes=result.model_dump(mode='json', include=_AUDIT_FIELDS),
            )
        return wrap_response(
            result.model_dump(mode='json'),
            message='Access grants have been updated successfully.',
        )


class UserGrantSetView(_GrantSetView):
    """Entidades que ve un usuario."""

    axis = GrantAxis.USER


class EntityGrantSetView(_GrantSetView):
    """Usuarios que ven una entidad."""

    axis = GrantAxis.ENTITY
    permission_classes = [IsAuthenticated, IsCompanyMember, HasSubscriptionAccess]
    subscription_check_quota = False

    @validated_query(GrantSetQuery)
    def get(self, request, key_id: UUID, *, query: PaginatedQuery):
        scope = self._scope(query.filters['entity_type'], key_id)
        result = deps.get_grant_set(scope.entity_type).execute(request.user.company_id, scope)
        return wrap_response(result.model_dump(mode='json'), message='OK')

    @validated_body(ReplaceGrantSetBody)
    def put(self, request, key_id: UUID, *, body: dict):
        scope = self._scope(body['entity_type'], key_id)
        result = deps.replace_grant_set(scope.entity_type).execute(
            request.user.company_id, scope, GrantSetInput(ids=body['ids']), request.user.id,
        )
        if result.changed:
            audit_log(
                request, _AUDIT_ENTITY, key_id, 'UPDATE',
                f'Access grants updated from {self.axis.value}',
                changes=result.model_dump(mode='json', include=_AUDIT_FIELDS),
            )
        return wrap_response(
            result.model_dump(mode='json'),
            message='Access grants have been updated successfully.',
        )
