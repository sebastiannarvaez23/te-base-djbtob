import uuid
from typing import List, Optional

from platform.features.integrations.connector_catalog.connector_catalog.domain.interfaces import IConnectorCatalogRepository
from platform.features.integrations.connector_catalog.connector_catalog.domain.schemas import (
    ConnectorDefinitionSchema,
    CreateConnectorDefinitionSchema,
    UpdateConnectorDefinitionSchema,
)
from platform.features.integrations.connector_catalog.connector_catalog.models import ConnectorDefinition


class DjangoConnectorCatalogRepository(IConnectorCatalogRepository):

    def get_all(self, *, active_only: bool = False) -> List[ConnectorDefinitionSchema]:
        qs = ConnectorDefinition.objects.all().order_by('key')
        if active_only:
            qs = qs.filter(is_active=True)
        return [ConnectorDefinitionSchema.model_validate(row) for row in qs]

    def get_by_id(self, id: uuid.UUID) -> Optional[ConnectorDefinitionSchema]:
        row = ConnectorDefinition.objects.filter(id=id).first()
        return ConnectorDefinitionSchema.model_validate(row) if row else None

    def get_by_key(self, key: str) -> Optional[ConnectorDefinitionSchema]:
        row = ConnectorDefinition.objects.filter(key=key).first()
        return ConnectorDefinitionSchema.model_validate(row) if row else None

    def create(self, data: CreateConnectorDefinitionSchema) -> ConnectorDefinitionSchema:
        row = ConnectorDefinition.objects.create(**data.model_dump())
        return ConnectorDefinitionSchema.model_validate(row)

    def update(
        self, id: uuid.UUID, data: UpdateConnectorDefinitionSchema,
    ) -> Optional[ConnectorDefinitionSchema]:
        row = ConnectorDefinition.objects.filter(id=id).first()
        if not row:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        row.save()
        return ConnectorDefinitionSchema.model_validate(row)

    def delete(self, id: uuid.UUID) -> bool:
        deleted, _ = ConnectorDefinition.objects.filter(id=id).delete()
        return deleted > 0
