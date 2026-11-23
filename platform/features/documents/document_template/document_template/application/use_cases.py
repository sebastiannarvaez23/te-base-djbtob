import uuid
from typing import List, Optional

from core.errors import AppErrorCode, ConflictException

from ..domain.interfaces import IDocumentTemplateRepository
from ..domain.schemas import (
    CreateDocumentTemplateSchema,
    DocumentTemplateListItemSchema,
    DocumentTemplateSchema,
    UpdateDocumentTemplateSchema,
)
from ..domain.template_validation import validate_template_sync
from core.trace import trace_layer


class GetAllDocumentTemplatesUseCase:
    def __init__(self, repository: IDocumentTemplateRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self,
        filters: dict | None = None,
        *,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[List[DocumentTemplateListItemSchema], int]:
        return self.repository.get_all(filters=filters, offset=offset, limit=limit)


class GetDocumentTemplateByIdUseCase:
    def __init__(self, repository: IDocumentTemplateRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID) -> Optional[DocumentTemplateSchema]:
        return self.repository.get_by_id(id)


class CreateDocumentTemplateUseCase:
    def __init__(self, repository: IDocumentTemplateRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateDocumentTemplateSchema) -> DocumentTemplateSchema:
        existing = self.repository.get_by_code(data.code)
        if existing:
            raise ConflictException(
                AppErrorCode.DOC_DUPLICATE_CODE,
                override_detail=f"A document template with code '{data.code}' already exists.",
            )
        return self.repository.create(data)


class UpdateDocumentTemplateUseCase:
    def __init__(self, repository: IDocumentTemplateRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID, data: UpdateDocumentTemplateSchema) -> Optional[DocumentTemplateSchema]:
        current = self.repository.get_by_id(id)
        if current is None:
            return None
        if data.code is not None:
            existing = self.repository.get_by_code(data.code)
            if existing and existing.id != id:
                raise ConflictException(
                    AppErrorCode.DOC_DUPLICATE_CODE,
                    override_detail=f"A document template with code '{data.code}' already exists.",
                )
        patch = data.model_dump(exclude_unset=True)
        merged = current.model_copy(update=patch)
        validate_template_sync(
            allowed_formats=merged.allowed_formats,
            default_format=merged.default_format,
            format_configs=merged.format_configs,
            is_storable=merged.is_storable,
            storage_path_template=merged.storage_path_template,
        )
        return self.repository.update(id, data)


class DeleteDocumentTemplateUseCase:
    def __init__(self, repository: IDocumentTemplateRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID) -> bool:
        return self.repository.delete(id)
