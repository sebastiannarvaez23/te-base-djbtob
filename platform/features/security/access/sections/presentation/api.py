from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, NotFoundException
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication
from platform.features.security.catalog_order import parse_uuid_ids
from platform.features.security.access.sections.application.use_cases import (
    CreateSectionUseCase,
    DeleteSectionUseCase,
    GetSectionUseCase,
    ListSectionsUseCase,
    ReorderSectionsUseCase,
    UpdateSectionUseCase,
)
from platform.features.security.access.sections.domain.schemas import CreateSectionSchema, UpdateSectionSchema
from platform.features.security.access.sections.infrastructure.repositories import DjangoSectionRepository
from platform.features.security.access.sections.presentation.bodies import (
    CreateSectionBody,
    ReorderSectionBody,
    UpdateSectionBody,
)
from platform.features.security.access.sections.presentation.queries import SectionListQuery


def _catalog_response(query, items):
    dumped = [s.model_dump() for s in items]
    if query.unpaginated:
        return wrap_response(dumped)
    total = len(dumped)
    page_items = dumped[query.offset: query.offset + query.page_size]
    return wrap_response({
        'items': page_items,
        'total': total,
        'page': query.page,
        'page_size': query.page_size,
        'total_pages': (total + query.page_size - 1) // query.page_size if query.page_size else 1,
    })


class SectionListCreateAPIView(APIView):
    """List all sections and create a new one."""

    authentication_classes = [AdminTokenAuthentication]

    @validated_query(SectionListQuery)
    def get(self, request, *, query: PaginatedQuery):
        sections = ListSectionsUseCase(DjangoSectionRepository()).execute(filters=query.filters)
        return _catalog_response(query, sections)

    @validated_body(CreateSectionBody)
    def post(self, request, *, body: dict):

        schema = CreateSectionSchema(**body)
        section = CreateSectionUseCase(DjangoSectionRepository()).execute(schema)
        audit_log(request, 'Section', section.id, 'CREATE', f'Section created: {schema.code}')
        return wrap_response(section.model_dump(), status_code=201, message='Section created successfully.')


class SectionReorderAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]

    @validated_body(ReorderSectionBody)
    def patch(self, request, *, body: dict):
        ids = parse_uuid_ids(body['ids'])
        count = ReorderSectionsUseCase(DjangoSectionRepository()).execute(ids)
        audit_log(request, 'Section', '', 'REORDER', f'count={count}')
        return wrap_response({'count': count})


class SectionDetailAPIView(APIView):
    """Retrieve, update and delete a specific section."""

    authentication_classes = [AdminTokenAuthentication]

    def get(self, request, section_id):
        result = GetSectionUseCase(DjangoSectionRepository()).execute(section_id)
        if not result:
            raise NotFoundException(AppErrorCode.SECTION_NOT_FOUND)
        return wrap_response(result.model_dump())

    @validated_body(UpdateSectionBody)
    def patch(self, request, section_id, *, body: dict):

        schema = UpdateSectionSchema(**body)
        section = UpdateSectionUseCase(DjangoSectionRepository()).execute(section_id, schema)
        if not section:
            raise NotFoundException(AppErrorCode.SECTION_NOT_FOUND)
        audit_log(request, 'Section', section_id, 'UPDATE', changes=body)
        return wrap_response(section.model_dump())

    def delete(self, request, section_id):
        deleted = DeleteSectionUseCase(DjangoSectionRepository()).execute(section_id)
        if not deleted:
            raise NotFoundException(AppErrorCode.SECTION_NOT_FOUND)
        audit_log(request, 'Section', section_id, 'DELETE')
        return Response(status=status.HTTP_204_NO_CONTENT)
