"""
TemplateLoader — fetches a template by code via the repository port.
"""
from core.errors import AppErrorCode, AppException, NotFoundException

from ...domain.interfaces import IDocumentTemplateRepository
from ...domain.schemas import DocumentTemplateSchema


class TemplateLoader:

    def __init__(self, repository: IDocumentTemplateRepository):
        self.repository = repository

    def load(self, code: str) -> DocumentTemplateSchema:
        template = self.repository.get_by_code(code)
        if template is None:
            raise NotFoundException(
                AppErrorCode.DOC_TEMPLATE_NOT_FOUND,
                override_detail=f'Document template "{code}" does not exist.',
            )

        if not template.is_active:
            raise AppException(
                AppErrorCode.DOC_TEMPLATE_INACTIVE,
                override_detail=f'Document template "{code}" is inactive.',
            )

        return template
