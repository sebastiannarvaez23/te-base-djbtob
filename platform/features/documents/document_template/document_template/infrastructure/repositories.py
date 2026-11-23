import uuid
from typing import List, Optional

from ..domain.interfaces import IDocumentTemplateRepository
from ..domain.schemas import (
    CreateDocumentTemplateSchema,
    DocumentTemplateListItemSchema,
    DocumentTemplateSchema,
    UpdateDocumentTemplateSchema,
)
from ..models import DocumentTemplate

_LIST_FIELDS = (
    'id', 'code', 'name', 'kind', 'description', 'is_active', 'is_storable',
)


def _to_list_item(obj: DocumentTemplate) -> DocumentTemplateListItemSchema:
    return DocumentTemplateListItemSchema(
        id=obj.id,
        code=obj.code,
        name=obj.name,
        kind=obj.kind,
        description=obj.description,
        is_active=obj.is_active,
        is_storable=obj.is_storable,
    )


def _to_schema(obj: DocumentTemplate) -> DocumentTemplateSchema:
    return DocumentTemplateSchema(
        id=obj.id,
        code=obj.code,
        name=obj.name,
        kind=obj.kind,
        html_template=obj.html_template,
        mock_data=obj.mock_data or {},
        description=obj.description,
        is_active=obj.is_active,
        allowed_formats=obj.allowed_formats or [],
        default_format=obj.default_format,
        format_configs=obj.format_configs or {},
        is_storable=obj.is_storable,
        storage_bucket=obj.storage_bucket,
        storage_path_template=obj.storage_path_template,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


class DjangoDocumentTemplateRepository(IDocumentTemplateRepository):

    def _qs(self):
        return DocumentTemplate.objects.all()

    def get_all(
        self,
        filters: dict | None = None,
        *,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[List[DocumentTemplateListItemSchema], int]:
        from django.db.models import Q

        qs = self._qs().only(*_LIST_FIELDS).order_by('kind', 'code')
        f = filters or {}
        if 'code' in f:
            qs = qs.filter(code__icontains=f['code'])
        if 'name' in f:
            qs = qs.filter(name__icontains=f['name'])
        if 'kind' in f:
            qs = qs.filter(kind=f['kind'])
        if 'is_active' in f:
            qs = qs.filter(is_active=f['is_active'])
        if 'is_storable' in f:
            qs = qs.filter(is_storable=f['is_storable'])
        if 'q' in f:
            q = f['q']
            qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q))
        total = qs.count()
        if limit is not None:
            qs = qs[max(0, offset): max(0, offset) + max(1, limit)]
        return [_to_list_item(obj) for obj in qs], total

    def get_by_id(self, id: uuid.UUID) -> Optional[DocumentTemplateSchema]:
        try:
            return _to_schema(self._qs().get(id=id))
        except DocumentTemplate.DoesNotExist:
            return None

    def get_by_code(self, code: str) -> Optional[DocumentTemplateSchema]:
        try:
            return _to_schema(self._qs().get(code=code))
        except DocumentTemplate.DoesNotExist:
            return None

    def create(self, data: CreateDocumentTemplateSchema) -> DocumentTemplateSchema:
        obj = DocumentTemplate.objects.create(**data.model_dump())
        return _to_schema(obj)

    def update(self, id: uuid.UUID, data: UpdateDocumentTemplateSchema) -> Optional[DocumentTemplateSchema]:
        try:
            obj = self._qs().get(id=id)
            fields = data.model_dump(exclude_unset=True)
            for field, value in fields.items():
                setattr(obj, field, value)
            obj.save()
            return _to_schema(obj)
        except DocumentTemplate.DoesNotExist:
            return None

    def delete(self, id: uuid.UUID) -> bool:
        try:
            DocumentTemplate.objects.get(id=id).delete()
            return True
        except DocumentTemplate.DoesNotExist:
            return False
