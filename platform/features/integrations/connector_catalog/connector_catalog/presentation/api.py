from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication

from platform.features.integrations.connector_catalog.connector_catalog.application.health import GetIntegrationHealthUseCase
from platform.features.integrations.connector_catalog.connector_catalog.application.use_cases import (
    CreateConnectorDefinitionUseCase,
    DeleteConnectorDefinitionUseCase,
    GetConnectorDefinitionUseCase,
    ListConnectorDefinitionsUseCase,
    UpdateConnectorDefinitionUseCase,
)
from platform.features.integrations.connector_catalog.connector_catalog.domain.schemas import (
    CreateConnectorDefinitionSchema,
    UpdateConnectorDefinitionSchema,
)
from platform.features.integrations.connector_catalog.connector_catalog.infrastructure.repositories import (
    DjangoConnectorCatalogRepository,
)
from platform.features.integrations.connector_catalog.connector_catalog.presentation.bodies import (
    CreateConnectorDefinitionBody,
    UpdateConnectorDefinitionBody,
)
from platform.features.integrations.connector_catalog.connector_catalog.presentation.queries import (
    ConnectorCatalogListQuery,
)


def _repo():
    return DjangoConnectorCatalogRepository()


def _dump(schema) -> dict:
    return schema.model_dump(mode='json')


class ConnectorCatalogListCreateView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(ConnectorCatalogListQuery)
    def get(self, request, *, query: PaginatedQuery):
        active_only = bool(query.filters.get('active_only', False))
        result = ListConnectorDefinitionsUseCase(_repo()).execute(active_only=active_only)
        return wrap_response([_dump(item) for item in result])

    @validated_body(CreateConnectorDefinitionBody)
    def post(self, request, *, body: dict):
        schema = CreateConnectorDefinitionSchema(**body)
        result = CreateConnectorDefinitionUseCase(_repo()).execute(schema)
        audit_log(request, 'ConnectorDefinition', result.id, 'CREATE', f'Connector: {result.key}')
        return wrap_response(_dump(result), status_code=201, message='Connector created.')


class ConnectorCatalogDetailView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        result = GetConnectorDefinitionUseCase(_repo()).execute(pk)
        return wrap_response(_dump(result))

    @validated_body(UpdateConnectorDefinitionBody)
    def patch(self, request, pk, *, body: dict):
        schema = UpdateConnectorDefinitionSchema(**body)
        result = UpdateConnectorDefinitionUseCase(_repo()).execute(pk, schema)
        audit_log(request, 'ConnectorDefinition', pk, 'UPDATE', changes=request.data)
        return wrap_response(_dump(result))

    def delete(self, request, pk):
        DeleteConnectorDefinitionUseCase(_repo()).execute(pk)
        audit_log(request, 'ConnectorDefinition', pk, 'DELETE', 'Connector deleted')
        return wrap_response(None, message='Connector deleted.')


class IntegrationHealthView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return wrap_response(GetIntegrationHealthUseCase().execute())
