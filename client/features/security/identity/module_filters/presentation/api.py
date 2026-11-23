import json

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.permissions import HasSubscriptionAccess, IsCompanyMember
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from client.features.security.identity.module_filters.application.use_cases import (
    ActivateModuleFilterUseCase,
    CreateModuleFilterUseCase,
    DeactivateModuleFiltersUseCase,
    DeleteModuleFilterUseCase,
    ListModuleFiltersUseCase,
    UpdateModuleFilterUseCase,
)
from client.features.security.identity.module_filters.domain.schemas import (
    ModuleFilterInput,
    ModuleFilterPatch,
    ModuleKey,
)
from client.features.security.identity.module_filters.infrastructure.facility_catalog import (
    DjangoFacilityCatalog,
)
from client.features.security.identity.module_filters.infrastructure.repositories import (
    DjangoModuleFilterRepository,
)
from client.features.security.identity.module_filters.presentation.bodies import (
    CreateModuleFilterBody,
    DeactivateModuleFiltersBody,
    UpdateModuleFilterBody,
)
from client.features.security.identity.module_filters.presentation.queries import (
    ModuleFilterListQuery,
)

_ENTITY = 'ModuleFilter'
_WAREHOUSE_FILTERS_FEATURES = (
    'warehouse.spaces.toolbar-avanced-filters',
    'warehouse.topology.toolbar-avanced-filters',
)


def _repository():
    return DjangoModuleFilterRepository()


def _catalog():
    return DjangoFacilityCatalog()


def _audit_changes(payload: dict) -> dict:
    return json.loads(json.dumps(payload, default=str))


def _preferred_warehouse_filters_feature(request) -> str:
    """Spaces and Topology share the filter catalog; either toolbar key is enough."""
    user = getattr(request, 'user', None)
    rol = getattr(user, 'rol', None) if user is not None else None
    role_id = getattr(user, 'rol_id', None) if user is not None else None
    role_id = role_id or (getattr(rol, 'id', None) if rol is not None else None)
    if not role_id:
        return _WAREHOUSE_FILTERS_FEATURES[0]
    from core.access.role_cache import RoleFeatureCache
    role_keys = RoleFeatureCache.get_or_load(str(role_id))
    for key in _WAREHOUSE_FILTERS_FEATURES:
        if key in role_keys:
            return key
    return _WAREHOUSE_FILTERS_FEATURES[0]


def _feature_for_saved_filter(request, filter_id) -> str | None:
    """Warehouse presets keep their toolbar gate. Other modules are not gated here."""
    if not filter_id:
        return _preferred_warehouse_filters_feature(request)
    from client.features.security.identity.module_filters.models import ModuleFilter
    row = ModuleFilter.objects.filter(pk=filter_id).only('module_key').first()
    if row is None:
        return None
    return _warehouse_filters_feature(row.module_key, request)


def _warehouse_filters_feature(module_key: str | None, request=None) -> str | None:
    if module_key != ModuleKey.WAREHOUSE.value:
        return None
    if request is None:
        return _WAREHOUSE_FILTERS_FEATURES[0]
    return _preferred_warehouse_filters_feature(request)


class ModuleFilterListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyMember, HasSubscriptionAccess]
    subscription_check_quota = False

    def get_subscription_functionality(self, request):
        if request.method == 'GET':
            return _warehouse_filters_feature(request.query_params.get('module_key'), request)
        data = getattr(request, 'data', None) or {}
        module_key = data.get('module_key') if isinstance(data, dict) else None
        return _warehouse_filters_feature(module_key, request)

    @validated_query(ModuleFilterListQuery)
    def get(self, request, *, query: PaginatedQuery):
        result = ListModuleFiltersUseCase(_repository(), _catalog()).execute(
            request.user.id, ModuleKey(query.filters['module_key']),
        )
        return wrap_response(result.model_dump(mode='json'), message='OK')

    @validated_body(CreateModuleFilterBody)
    def post(self, request, *, body: dict):
        result = CreateModuleFilterUseCase(_repository(), _catalog()).execute(
            request.user.id, ModuleFilterInput(**body),
        )
        audit_log(
            request, _ENTITY, result.id, 'CREATE',
            'Advanced filter created',
            changes=_audit_changes(body),
        )
        return wrap_response(
            result.model_dump(mode='json'),
            status_code=status.HTTP_201_CREATED,
            message='The advanced filter has been created successfully.',
        )


class ModuleFilterDetailView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyMember, HasSubscriptionAccess]
    subscription_check_quota = False

    def get_subscription_functionality(self, request):
        return _feature_for_saved_filter(request, self.kwargs.get('filter_id'))

    @validated_body(UpdateModuleFilterBody)
    def patch(self, request, filter_id, *, body: dict):
        result = UpdateModuleFilterUseCase(_repository(), _catalog()).execute(
            request.user.id, filter_id, ModuleFilterPatch(**body),
        )
        audit_log(
            request, _ENTITY, filter_id, 'UPDATE',
            'Advanced filter updated',
            changes=_audit_changes(body),
        )
        return wrap_response(
            result.model_dump(mode='json'),
            message='The advanced filter has been updated successfully.',
        )

    def delete(self, request, filter_id):
        DeleteModuleFilterUseCase(_repository()).execute(request.user.id, filter_id)
        audit_log(request, _ENTITY, filter_id, 'DELETE', 'Advanced filter deleted')
        return wrap_response(
            {'deleted': True, 'filter_id': str(filter_id)},
            message='The advanced filter has been deleted successfully.',
        )


class ModuleFilterActivateView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyMember, HasSubscriptionAccess]
    subscription_check_quota = False

    def get_subscription_functionality(self, request):
        return _feature_for_saved_filter(request, self.kwargs.get('filter_id'))

    def post(self, request, filter_id):
        result = ActivateModuleFilterUseCase(_repository(), _catalog()).execute(
            request.user.id, filter_id,
        )
        audit_log(request, _ENTITY, filter_id, 'UPDATE', 'Advanced filter activated')
        return wrap_response(
            result.model_dump(mode='json'),
            message='The advanced filter is now active.',
        )


class ModuleFilterDeactivateView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyMember, HasSubscriptionAccess]
    subscription_check_quota = False

    def get_subscription_functionality(self, request):
        data = getattr(request, 'data', None) or {}
        module_key = data.get('module_key') if isinstance(data, dict) else None
        return _warehouse_filters_feature(module_key, request)

    @validated_body(DeactivateModuleFiltersBody)
    def post(self, request, *, body: dict):
        module_key = ModuleKey(body['module_key'])
        DeactivateModuleFiltersUseCase(_repository()).execute(request.user.id, module_key)
        audit_log(request, _ENTITY, module_key.value, 'UPDATE', 'Advanced filters deactivated')
        return wrap_response(
            {'module_key': module_key.value, 'active_id': None},
            message='Advanced filters are off for this module.',
        )
