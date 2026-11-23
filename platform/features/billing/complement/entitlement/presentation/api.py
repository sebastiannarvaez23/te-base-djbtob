import uuid

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication
from platform.features.billing.complement.entitlement.application.use_cases import (
    GrantCompanyComplementUseCase,
    ListCompanyComplementsUseCase,
    ListComplementCatalogUseCase,
    RevokeCompanyComplementUseCase,
)
from platform.features.billing.complement.entitlement.domain.schemas import (
    GrantComplementSchema,
    RevokeComplementSchema,
)
from platform.features.billing.complement.entitlement.infrastructure.repositories import (
    DjangoCompanyComplementRepository,
)
from platform.features.billing.complement.entitlement.presentation.bodies import (
    GrantComplementBody,
    RevokeComplementBody,
)
from platform.features.billing.complement.entitlement.presentation.queries import (
    CompanyComplementQuery,
    ComplementCatalogQuery,
)


def _repo():
    return DjangoCompanyComplementRepository()


def _page(result):
    return wrap_response({
        'items': [item.model_dump(mode='json') for item in result.items],
        'total': result.total,
        'page': result.page,
        'page_size': result.page_size,
        'total_pages': result.total_pages,
    })


def _admin_id(request) -> uuid.UUID | None:
    raw = getattr(request.user, 'id', None)
    if isinstance(raw, uuid.UUID):
        return raw
    return None


def _as_uuid(value) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


class ComplementCatalogView(APIView):
    """Paginated catalog of functionalities sold as complements."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(ComplementCatalogQuery)
    def get(self, request, *, query: PaginatedQuery):
        result = ListComplementCatalogUseCase(_repo()).execute(query)
        return _page(result)


class CompanyComplementListCreateView(APIView):
    """List or activate complement licenses for one company."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(CompanyComplementQuery)
    def get(self, request, company_id: uuid.UUID, *, query: PaginatedQuery):
        result = ListCompanyComplementsUseCase(_repo()).execute(company_id, query)
        return _page(result)

    @validated_body(GrantComplementBody)
    def post(self, request, company_id: uuid.UUID, *, body: dict):
        functionality_id = body.get('functionality_id')
        module_id = body.get('module_id')
        schema = GrantComplementSchema(
            company_id=company_id,
            functionality_id=_as_uuid(functionality_id) if functionality_id else None,
            module_id=_as_uuid(module_id) if module_id else None,
            notes=body.get('notes') or '',
            granted_by_id=_admin_id(request),
        )
        created = GrantCompanyComplementUseCase(_repo()).execute(schema)
        audit_log(
            request, 'CompanyComplement', created.id, 'GRANT',
            changes={
                'company_id': str(company_id),
                'functionality_id': str(functionality_id) if functionality_id else None,
                'module_id': str(module_id) if module_id else None,
            },
        )
        return wrap_response(
            created.model_dump(mode='json'),
            status_code=201,
            message='Complement activated.',
        )


class CompanyComplementRevokeView(APIView):
    """Close an active complement license."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(RevokeComplementBody)
    def post(self, request, company_id: uuid.UUID, entitlement_id: uuid.UUID, *, body: dict):
        schema = RevokeComplementSchema(
            company_id=company_id,
            entitlement_id=entitlement_id,
            notes=body.get('notes') or '',
        )
        revoked = RevokeCompanyComplementUseCase(_repo()).execute(schema)
        audit_log(
            request, 'CompanyComplement', entitlement_id, 'REVOKE',
            changes={'company_id': str(company_id)},
        )
        return wrap_response(revoked.model_dump(mode='json'), message='Complement revoked.')
