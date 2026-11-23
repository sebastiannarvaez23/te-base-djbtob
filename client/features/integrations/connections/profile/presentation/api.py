from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.permissions import HasSubscriptionAccess, IsCompanyMember
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body

from client.features.integrations.connections.profile.application.connection_use_cases import (
    CreateConnectionUseCase,
    ListConnectionsUseCase,
    TestConnectionUseCase,
    UpdateConnectionUseCase,
)
from client.features.integrations.connections.profile.application.mapping_use_cases import (
    CreateFieldMappingUseCase,
    DeleteFieldMappingUseCase,
    ListFieldMappingsUseCase,
    UpdateFieldMappingUseCase,
)
from client.features.integrations.connections.profile.domain.schemas import CreateConnectionSchema, CreateFieldMappingSchema, UpdateConnectionSchema, UpdateFieldMappingSchema
from client.features.integrations.connections.profile.infrastructure.repositories import DjangoSyncRunRepository
from client.features.integrations.connections.profile.presentation.bodies import (
    CreateConnectionBody,
    CreateFieldMappingBody,
    UpdateConnectionBody,
    UpdateFieldMappingBody,
)
from client.features.integrations.connections.profile.presentation.queries import ConnectionListQuery, ConnectionRelatedQuery


class IntegrationConnectionListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyMember, HasSubscriptionAccess]
    subscription_functionality = {
        'get': 'integrations.erp-integration',
        'post': 'integrations.erp-integration',
    }

    @validated_query(ConnectionListQuery)
    def get(self, request, *, query: PaginatedQuery):
        result = ListConnectionsUseCase().execute(query)
        items = [item.model_dump(mode='json') for item in result.items]
        if query.unpaginated:
            return wrap_response(items)
        return wrap_response({
            'items': items,
            'total': result.total,
            'page': result.page,
            'page_size': result.page_size,
            'total_pages': result.total_pages,
        })

    @validated_body(CreateConnectionBody)
    def post(self, request, *, body: dict):
        schema = CreateConnectionSchema(
            **body,
            created_by=getattr(request.user, 'id', None),
        )
        result = CreateConnectionUseCase().execute(schema, request.tenant.schema_name)
        audit_log(request, 'IntegrationConnection', result.id, 'CREATE', f'Connection: {result.name}')
        return wrap_response(result.model_dump(mode='json'), status_code=201, message='Connection created.')


class IntegrationConnectionDetailView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyMember, HasSubscriptionAccess]
    subscription_functionality = {
        'patch': 'integrations.erp-integration',
    }

    @validated_body(UpdateConnectionBody)
    def patch(self, request, pk, *, body: dict):
        schema = UpdateConnectionSchema(**body)
        result = UpdateConnectionUseCase().execute(pk, schema, request.tenant.schema_name)
        audit_log(request, 'IntegrationConnection', pk, 'UPDATE', changes=request.data)
        return wrap_response(result.model_dump(mode='json'))


class IntegrationConnectionTestView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyMember, HasSubscriptionAccess]
    subscription_functionality = 'integrations.erp-integration'

    def post(self, request, pk):
        result = TestConnectionUseCase().execute(
            pk, request.tenant.schema_name, request_id=getattr(request, 'request_id', '-'),
        )
        return wrap_response(result.model_dump(mode='json'), message='Connection test successful.')


class FieldMappingListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyMember, HasSubscriptionAccess]
    subscription_functionality = {
        'get': 'integrations.data-mapping',
        'post': 'integrations.data-mapping',
    }

    @validated_query(ConnectionRelatedQuery)
    def get(self, request, *, query: PaginatedQuery):
        connection_id = query.filters.get('connection_id')
        if not connection_id:
            return wrap_response([])
        import uuid as _uuid
        data = ListFieldMappingsUseCase().execute(_uuid.UUID(connection_id))
        return wrap_response([item.model_dump(mode='json') for item in data])

    @validated_body(CreateFieldMappingBody)
    def post(self, request, *, body: dict):
        schema = CreateFieldMappingSchema(**body)
        result = CreateFieldMappingUseCase().execute(schema)
        return wrap_response(result.model_dump(mode='json'), status_code=201)


class FieldMappingDetailView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyMember, HasSubscriptionAccess]
    subscription_functionality = {
        'patch': 'integrations.data-mapping',
        'delete': 'integrations.data-mapping',
    }

    @validated_body(UpdateFieldMappingBody)
    def patch(self, request, pk, *, body: dict):
        schema = UpdateFieldMappingSchema(**body)
        result = UpdateFieldMappingUseCase().execute(pk, schema)
        return wrap_response(result.model_dump(mode='json'))

    def delete(self, request, pk):
        DeleteFieldMappingUseCase().execute(pk)
        return wrap_response(None, message='Mapping deleted.')


class SyncRunListView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyMember, HasSubscriptionAccess]
    subscription_functionality = 'integrations.integration-logs'

    @validated_query(ConnectionRelatedQuery)
    def get(self, request, *, query: PaginatedQuery):
        cid = query.filters.get('connection_id')
        data = DjangoSyncRunRepository().list_recent(cid)
        return wrap_response([item.model_dump(mode='json') for item in data])
