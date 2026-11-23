from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView

from client.features.logging.system.config.application.use_cases import (
    GetAllLogConfigsUseCase,
    GetLogConfigUseCase,
    UpdateLogConfigUseCase,
)
from client.features.logging.system.config.domain.schemas import LogRetentionConfigUpdateSchema
from client.features.logging.system.config.infrastructure.repositories import DjangoLogConfigRepository
from client.features.logging.system.config.presentation.bodies import UpdateLogConfigBody
from client.features.logging.system.config.presentation.queries import LogConfigListQuery
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, NotFoundException
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body


class LogConfigListAPIView(APIView):
    """Lista todas las configuraciones de log."""
    permission_classes = [IsAdminUser]

    @validated_query(LogConfigListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        result = GetAllLogConfigsUseCase(DjangoLogConfigRepository()).execute(query)
        items = [c.model_dump() for c in result.items]
        if query.unpaginated:
            return wrap_response(items)
        return wrap_response({
            'items': items,
            'total': result.total,
            'page': result.page,
            'page_size': result.page_size,
            'total_pages': result.total_pages,
        })


class LogConfigDetailAPIView(APIView):
    """Obtiene o actualiza la configuración de un tipo de log específico."""
    permission_classes = [IsAdminUser]

    def get(self, request, log_type, *args, **kwargs):
        config = GetLogConfigUseCase(DjangoLogConfigRepository()).execute(log_type)
        if not config:
            raise NotFoundException(AppErrorCode.VALIDATION_ERROR, override_detail='Configuration not found.')
        return wrap_response(config.model_dump())

    @validated_body(UpdateLogConfigBody)
    def put(self, request, log_type, *args, body: dict, **kwargs):

        update_data = LogRetentionConfigUpdateSchema(**body)
        config = UpdateLogConfigUseCase(DjangoLogConfigRepository()).execute(log_type, update_data)
        return wrap_response(config.model_dump())
