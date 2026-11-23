import uuid
from typing import List

from core.errors import AppErrorCode, NotFoundException, ValidationAppException

from ..domain.interfaces import IConnectorCatalogRepository
from ..domain.schemas import (
    ConnectorDefinitionSchema,
    CreateConnectorDefinitionSchema,
    UpdateConnectorDefinitionSchema,
)
from core.trace import trace_layer

VALID_KINDS = {'ERP', 'PROVIDER', 'APP'}


class ListConnectorDefinitionsUseCase:
    def __init__(self, repository: IConnectorCatalogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, *, active_only: bool = False) -> List[ConnectorDefinitionSchema]:
        return self.repository.get_all(active_only=active_only)


class GetConnectorDefinitionUseCase:
    def __init__(self, repository: IConnectorCatalogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID) -> ConnectorDefinitionSchema:
        result = self.repository.get_by_id(id)
        if not result:
            raise NotFoundException(
                AppErrorCode.INT_CONNECTOR_NOT_FOUND,
                override_detail='Connector definition not found.',
            )
        return result


class CreateConnectorDefinitionUseCase:
    def __init__(self, repository: IConnectorCatalogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateConnectorDefinitionSchema) -> ConnectorDefinitionSchema:
        if data.kind not in VALID_KINDS:
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail=f"Invalid kind '{data.kind}'.",
            )
        if self.repository.get_by_key(data.key):
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail=f"Connector key '{data.key}' already exists.",
            )
        return self.repository.create(data)


class UpdateConnectorDefinitionUseCase:
    def __init__(self, repository: IConnectorCatalogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID, data: UpdateConnectorDefinitionSchema) -> ConnectorDefinitionSchema:
        if data.kind is not None and data.kind not in VALID_KINDS:
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail=f"Invalid kind '{data.kind}'.",
            )
        result = self.repository.update(id, data)
        if not result:
            raise NotFoundException(
                AppErrorCode.INT_CONNECTOR_NOT_FOUND,
                override_detail='Connector definition not found.',
            )
        return result


class DeleteConnectorDefinitionUseCase:
    def __init__(self, repository: IConnectorCatalogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID) -> None:
        if not self.repository.delete(id):
            raise NotFoundException(
                AppErrorCode.INT_CONNECTOR_NOT_FOUND,
                override_detail='Connector definition not found.',
            )
