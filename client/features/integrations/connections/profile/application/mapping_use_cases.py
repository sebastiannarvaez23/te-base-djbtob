"""Use cases de mapeos."""

from __future__ import annotations

import uuid

from core.errors import AppErrorCode, NotFoundException

from client.features.integrations.connections.profile.application.mapping_engine import validate_mapping_rules
from client.features.integrations.connections.profile.domain.schemas import CreateFieldMappingSchema, UpdateFieldMappingSchema
from client.features.integrations.connections.profile.infrastructure.repositories import (
    DjangoConnectionRepository,
    DjangoFieldMappingRepository,
)
from core.trace import trace_layer


class ListFieldMappingsUseCase:
    @trace_layer('application')
    def execute(self, connection_id: uuid.UUID):
        if not DjangoConnectionRepository().get_by_id(connection_id):
            raise NotFoundException(
                AppErrorCode.INT_CONNECTOR_NOT_FOUND,
                override_detail='Connection not found.',
            )
        return DjangoFieldMappingRepository().list_by_connection(connection_id)


class CreateFieldMappingUseCase:
    @trace_layer('application')
    def execute(self, data: CreateFieldMappingSchema):
        validate_mapping_rules(data.rules)
        if not DjangoConnectionRepository().get_by_id(data.connection_id):
            raise NotFoundException(
                AppErrorCode.INT_CONNECTOR_NOT_FOUND,
                override_detail='Connection not found.',
            )
        return DjangoFieldMappingRepository().create(data)


class UpdateFieldMappingUseCase:
    @trace_layer('application')
    def execute(self, mapping_id: uuid.UUID, data: UpdateFieldMappingSchema):
        if data.rules is not None:
            validate_mapping_rules(data.rules)
        result = DjangoFieldMappingRepository().update(mapping_id, data)
        if not result:
            raise NotFoundException(
                AppErrorCode.INT_INVALID_MAPPING,
                override_detail='Mapping not found.',
            )
        return result


class DeleteFieldMappingUseCase:
    @trace_layer('application')
    def execute(self, mapping_id: uuid.UUID):
        if not DjangoFieldMappingRepository().delete(mapping_id):
            raise NotFoundException(
                AppErrorCode.INT_INVALID_MAPPING,
                override_detail='Mapping not found.',
            )
