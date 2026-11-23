import uuid

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, ConflictException
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication
from platform.features.security.catalog_order import parse_uuid_ids
from platform.features.security.access.roles.application.catalog_use_cases import (
    CreateAdminCatalogFeatureUseCase,
    CreateAdminCatalogModuleUseCase,
    CreateAdminSectionUseCase,
    DeleteAdminCatalogFeatureUseCase,
    DeleteAdminCatalogModuleUseCase,
    DeleteAdminSectionUseCase,
    ListAdminCatalogFeaturesUseCase,
    ListAdminCatalogModulesUseCase,
    ListAdminSectionsUseCase,
    ReorderAdminCatalogModulesUseCase,
    ReorderAdminSectionsUseCase,
    ToggleAdminCatalogModuleUseCase,
    ToggleAdminSectionUseCase,
    UpdateAdminCatalogFeatureUseCase,
    UpdateAdminCatalogModuleUseCase,
    UpdateAdminSectionUseCase,
)
from platform.features.security.access.roles.domain.catalog_schemas import (
    CreateAdminFeatureSchema,
    CreateAdminModuleSchema,
    CreateAdminSectionSchema,
    UpdateAdminFeatureSchema,
    UpdateAdminModuleSchema,
    UpdateAdminSectionSchema,
)
from platform.features.security.access.roles.infrastructure.catalog_repositories import DjangoAdminCatalogRepository
from platform.features.security.access.roles.presentation.bodies import (
    CreateAdminFeatureBody,
    CreateAdminModuleBody,
    CreateAdminSectionBody,
    ReorderCatalogBody,
    UpdateAdminFeatureBody,
    UpdateAdminModuleBody,
    UpdateAdminSectionBody,
)
from platform.features.security.access.roles.presentation.queries import (
    CatalogFeatureListQuery,
    CatalogListQuery,
    SectionListQuery,
)


def _repo():
    return DjangoAdminCatalogRepository()


def _catalog_response(query, items):
    dumped = [i.model_dump(mode='json') for i in items]
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


class AdminCatalogSectionListCreateAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(SectionListQuery)
    def get(self, request, *, query: PaginatedQuery):
        sections = ListAdminSectionsUseCase(_repo()).execute(filters=query.filters)
        return _catalog_response(query, sections)

    @validated_body(CreateAdminSectionBody)
    def post(self, request, *, body: dict):
        section = CreateAdminSectionUseCase(_repo()).execute(CreateAdminSectionSchema(**body))
        audit_log(request, 'AdminSection', section.id, 'CREATE', f'Section created: {section.code}')
        return wrap_response(section.model_dump(mode='json'), status_code=201)


class AdminCatalogSectionDetailAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(UpdateAdminSectionBody)
    def patch(self, request, section_id: uuid.UUID, *, body: dict):
        section = UpdateAdminSectionUseCase(_repo()).execute(
            section_id, UpdateAdminSectionSchema(**body),
        )
        audit_log(request, 'AdminSection', section_id, 'UPDATE', changes=body)
        return wrap_response(section.model_dump(mode='json'))

    def delete(self, request, section_id: uuid.UUID):
        DeleteAdminSectionUseCase(_repo()).execute(section_id)
        audit_log(request, 'AdminSection', section_id, 'DELETE')
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminCatalogSectionReorderAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(ReorderCatalogBody)
    def patch(self, request, *, body: dict):
        ids = parse_uuid_ids(body['ids'])
        ReorderAdminSectionsUseCase(_repo()).execute(ids)
        audit_log(request, 'AdminSection', '', 'REORDER', f'count={len(ids)}')
        return wrap_response({'count': len(ids)})


class AdminCatalogSectionToggleAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, section_id: uuid.UUID):
        section = ToggleAdminSectionUseCase(_repo()).execute(section_id)
        audit_log(request, 'AdminSection', section_id, 'TOGGLE', f'is_active={section.is_active}')
        return wrap_response(section.model_dump(mode='json'))


class AdminCatalogModuleListCreateAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(CatalogListQuery)
    def get(self, request, *, query: PaginatedQuery):
        result = ListAdminCatalogModulesUseCase(_repo()).execute(
            page=query.page, page_size=query.page_size,
        )
        return wrap_response(result.model_dump(mode='json'))

    @validated_body(CreateAdminModuleBody)
    def post(self, request, *, body: dict):
        module = CreateAdminCatalogModuleUseCase(_repo()).execute(CreateAdminModuleSchema(**body))
        audit_log(request, 'AdminModule', module.id, 'CREATE', f'Module created: {module.code}')
        return wrap_response(module.model_dump(mode='json'), status_code=201)


class AdminCatalogModuleDetailAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(UpdateAdminModuleBody)
    def patch(self, request, module_id: uuid.UUID, *, body: dict):
        module = UpdateAdminCatalogModuleUseCase(_repo()).execute(
            module_id, UpdateAdminModuleSchema(**body),
        )
        audit_log(request, 'AdminModule', module_id, 'UPDATE', changes=body)
        return wrap_response(module.model_dump(mode='json'))

    def delete(self, request, module_id: uuid.UUID):
        from django.db import IntegrityError
        from django.db.models.deletion import ProtectedError
        try:
            DeleteAdminCatalogModuleUseCase(_repo()).execute(module_id)
        except (ProtectedError, IntegrityError) as exc:
            raise ConflictException(AppErrorCode.MODULE_HAS_DEPENDENCIES) from exc
        audit_log(request, 'AdminModule', module_id, 'DELETE')
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminCatalogModuleReorderAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(ReorderCatalogBody)
    def patch(self, request, *, body: dict):
        ids = parse_uuid_ids(body['ids'])
        ReorderAdminCatalogModulesUseCase(_repo()).execute(ids)
        audit_log(request, 'AdminModule', '', 'REORDER', f'count={len(ids)}')
        return wrap_response({'count': len(ids)})


class AdminCatalogModuleToggleAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, module_id: uuid.UUID):
        module = ToggleAdminCatalogModuleUseCase(_repo()).execute(module_id)
        audit_log(request, 'AdminModule', module_id, 'TOGGLE', f'is_active={module.is_active}')
        return wrap_response(module.model_dump(mode='json'))


class AdminCatalogFeatureListCreateAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(CatalogFeatureListQuery)
    def get(self, request, *, query: PaginatedQuery):
        f = query.filters
        module_id = uuid.UUID(f['module_id']) if f.get('module_id') else None
        result = ListAdminCatalogFeaturesUseCase(_repo()).execute(
            page=query.page,
            page_size=query.page_size,
            module_code=f.get('module'),
            module_id=module_id,
            label=f.get('label'),
            key=f.get('key'),
            category=f.get('category'),
        )
        return wrap_response(result.model_dump(mode='json'))

    @validated_body(CreateAdminFeatureBody)
    def post(self, request, *, body: dict):
        feature = CreateAdminCatalogFeatureUseCase(_repo()).execute(CreateAdminFeatureSchema(**body))
        audit_log(request, 'AdminFeature', feature.id, 'CREATE', f'Feature created: {feature.key}')
        return wrap_response(feature.model_dump(mode='json'), status_code=201)


class AdminCatalogFeatureDetailAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(UpdateAdminFeatureBody)
    def patch(self, request, feature_id: uuid.UUID, *, body: dict):
        feature = UpdateAdminCatalogFeatureUseCase(_repo()).execute(
            feature_id, UpdateAdminFeatureSchema(**body),
        )
        audit_log(request, 'AdminFeature', feature_id, 'UPDATE', changes=body)
        return wrap_response(feature.model_dump(mode='json'))

    def delete(self, request, feature_id: uuid.UUID):
        DeleteAdminCatalogFeatureUseCase(_repo()).execute(feature_id)
        audit_log(request, 'AdminFeature', feature_id, 'DELETE')
        return Response(status=status.HTTP_204_NO_CONTENT)
