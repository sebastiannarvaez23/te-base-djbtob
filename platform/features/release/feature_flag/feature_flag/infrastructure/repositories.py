from __future__ import annotations

import uuid
from typing import List, Optional

from django.db import transaction

from core.flags.domain.enums import FlagStatus, FlagType, ScopeType
from core.flags.domain.schemas import FlagDefinition, FlagScope

from ..domain.interfaces import IFeatureFlagRepository
from ..domain.schemas import (
    CreateFeatureFlagSchema,
    FeatureFlagSchema,
    FeatureFlagScopeSchema,
    ScopeInputSchema,
    UpdateFeatureFlagSchema,
)
from ..models import FeatureFlag, FeatureFlagScope


def _scope_to_schema(obj: FeatureFlagScope) -> FeatureFlagScopeSchema:
    return FeatureFlagScopeSchema(
        id=obj.id,
        scope_type=obj.scope_type,
        scope_value=obj.scope_value,
        is_active=obj.is_active,
    )


def _to_schema(obj: FeatureFlag) -> FeatureFlagSchema:
    scopes = [_scope_to_schema(s) for s in obj.scopes.all()]
    return FeatureFlagSchema(
        id=obj.id,
        key=obj.key,
        name=obj.name,
        description=obj.description,
        flag_type=obj.flag_type,
        status=obj.status,
        enabled=obj.enabled,
        owner=obj.owner,
        scopes=scopes,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


def _replace_scopes(flag: FeatureFlag, scopes: List[ScopeInputSchema]) -> None:
    FeatureFlagScope.objects.filter(flag=flag).delete()
    FeatureFlagScope.objects.bulk_create([
        FeatureFlagScope(
            flag=flag,
            scope_type=scope.scope_type,
            scope_value=scope.scope_value,
            is_active=scope.is_active,
        )
        for scope in scopes
    ])


class DjangoFeatureFlagRepository(IFeatureFlagRepository):

    def _qs(self):
        return FeatureFlag.objects.prefetch_related('scopes')

    def get_all(self, filters: dict | None = None) -> List[FeatureFlagSchema]:
        from django.db.models import Q

        qs = self._qs().order_by('key')
        f = filters or {}
        if 'key' in f:
            qs = qs.filter(key__icontains=f['key'])
        if 'name' in f:
            qs = qs.filter(name__icontains=f['name'])
        if 'status' in f:
            qs = qs.filter(status=f['status'])
        if 'flag_type' in f:
            qs = qs.filter(flag_type=f['flag_type'])
        if 'enabled' in f:
            qs = qs.filter(enabled=f['enabled'])
        if 'owner' in f:
            qs = qs.filter(owner__icontains=f['owner'])
        if 'q' in f:
            q = f['q']
            qs = qs.filter(Q(key__icontains=q) | Q(name__icontains=q) | Q(owner__icontains=q))
        return [_to_schema(obj) for obj in qs]

    def get_by_id(self, id: uuid.UUID) -> Optional[FeatureFlagSchema]:
        try:
            return _to_schema(self._qs().get(id=id))
        except FeatureFlag.DoesNotExist:
            return None

    def get_by_key(self, key: str) -> Optional[FeatureFlagSchema]:
        try:
            return _to_schema(self._qs().get(key=key))
        except FeatureFlag.DoesNotExist:
            return None

    @transaction.atomic
    def create(self, data: CreateFeatureFlagSchema) -> FeatureFlagSchema:
        obj = FeatureFlag.objects.create(
            key=data.key,
            name=data.name,
            description=data.description,
            flag_type=data.flag_type,
            status=data.status,
            enabled=data.enabled,
            owner=data.owner,
        )
        if data.scopes:
            _replace_scopes(obj, data.scopes)
        return _to_schema(self._qs().get(id=obj.id))

    @transaction.atomic
    def update(
        self, id: uuid.UUID, data: UpdateFeatureFlagSchema,
    ) -> Optional[FeatureFlagSchema]:
        try:
            obj = FeatureFlag.objects.get(id=id)
        except FeatureFlag.DoesNotExist:
            return None

        fields = data.model_dump(exclude_unset=True)
        scopes = fields.pop('scopes', None)
        for field, value in fields.items():
            setattr(obj, field, value)
        obj.save()

        if scopes is not None:
            scope_inputs = [ScopeInputSchema(**s) for s in scopes]
            _replace_scopes(obj, scope_inputs)

        return _to_schema(self._qs().get(id=obj.id))

    @transaction.atomic
    def delete(self, id: uuid.UUID) -> bool:
        try:
            obj = FeatureFlag.objects.get(id=id)
        except FeatureFlag.DoesNotExist:
            return False
        FeatureFlagScope.objects.filter(flag=obj).delete()
        obj.delete()
        return True

    def get_active_definitions(self) -> List[FlagDefinition]:
        qs = (
            FeatureFlag.objects
            .filter(status=FlagStatus.ACTIVE.value)
            .prefetch_related('scopes')
            .order_by('key')
        )
        definitions: List[FlagDefinition] = []
        for obj in qs:
            scopes = [
                FlagScope(
                    scope_type=ScopeType(scope.scope_type),
                    scope_value=scope.scope_value,
                    is_active=scope.is_active,
                )
                for scope in obj.scopes.all()
            ]
            definitions.append(FlagDefinition(
                key=obj.key,
                flag_type=FlagType(obj.flag_type),
                status=FlagStatus(obj.status),
                enabled=obj.enabled,
                scopes=scopes,
            ))
        return definitions
