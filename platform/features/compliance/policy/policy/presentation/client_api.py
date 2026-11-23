"""API tenant: pendientes, lectura y firma de políticas client."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.permissions import IsCompanyMember
from core.query import PaginatedQuery, validated_query
from core.storage import MinioStorageService
from core.validators import validated_body
from platform.features.compliance.policy.policy.application.client_use_cases import (
    GetClientPolicyCountryContentUseCase,
    RequireActiveClientPolicyUseCase,
)
from platform.features.compliance.policy.policy.application.sign_use_cases import (
    ListPendingPoliciesUseCase,
    ListPolicySignaturesUseCase,
    SignPolicyUseCase,
    VerifyPolicySignatureUseCase,
)
from platform.features.compliance.policy.policy.domain.enums import PolicySubjectType
from platform.features.compliance.policy.policy.domain.schemas import (
    SignPolicyContextSchema,
    SignPolicySchema,
    SignatoryRef,
)
from platform.features.compliance.policy.policy.infrastructure.repositories import (
    DjangoPolicyRepository,
    DjangoPolicySignatureRepository,
)
from platform.features.compliance.policy.policy.presentation.bodies import SignPolicyBody
from platform.features.compliance.policy.policy.presentation.queries import (
    PendingPoliciesQuery,
    PolicySignaturesQuery,
)


def _repo():
    return DjangoPolicyRepository()


def _sig_repo():
    return DjangoPolicySignatureRepository()


def _storage():
    return MinioStorageService()


def _client_signatory(request) -> SignatoryRef:
    return SignatoryRef(
        subject_type=PolicySubjectType.CLIENT,
        subject_id=str(request.user.id),
        tenant_id=str(request.user.company_id),
    )


def _sign_context(request, *, channel: str = 'web') -> SignPolicyContextSchema:
    return SignPolicyContextSchema(
        ip_address=request.META.get('REMOTE_ADDR') or None,
        user_agent=request.META.get('HTTP_USER_AGENT') or None,
        request_id=getattr(request, 'request_id', None),
        channel=channel or 'web',
    )


def _catalog_response(query, items):
    dumped = [item.model_dump(mode='json') for item in items]
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


class ClientPendingPoliciesView(APIView):
    """Políticas client pendientes de firma para el usuario autenticado."""

    permission_classes = [IsAuthenticated, IsCompanyMember]

    @validated_query(PendingPoliciesQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        from platform.features.compliance.policy.policy.application.country_resolve import (
            resolve_company_policy_country,
        )

        country = (query.filters or {}).get('country')
        if country:
            try:
                from platform.features.compliance.policy.policy.domain.schemas import (
                    normalize_country,
                )
                country = normalize_country(str(country))
            except ValueError:
                return _catalog_response(query, [])
            company_country = resolve_company_policy_country(
                getattr(request.user, 'company', None),
            )
            if company_country and country != company_country:
                from core.errors import AppErrorCode, ValidationAppException
                raise ValidationAppException(AppErrorCode.POLICY_COUNTRY_MISMATCH)
        else:
            country = resolve_company_policy_country(getattr(request.user, 'company', None))
        if not country:
            return _catalog_response(query, [])
        from platform.features.compliance.policy.policy.application.required_policy_codes import (
            get_client_login_required_policy_codes,
        )

        items = ListPendingPoliciesUseCase(_sig_repo()).execute(
            subject=_client_signatory(request),
            country=country,
            policy_codes=get_client_login_required_policy_codes(),
        )
        return _catalog_response(query, items)


class ClientPublishedPolicyByCodeView(APIView):
    """Markdown publicado de una política client, por código y país de la empresa."""

    permission_classes = [IsAuthenticated, IsCompanyMember]

    def get(self, request, code, *args, **kwargs):
        from core.errors import AppErrorCode, ValidationAppException
        from platform.features.compliance.policy.policy.application.country_resolve import (
            resolve_company_policy_country,
        )
        from platform.features.compliance.policy.policy.application.public_use_cases import (
            GetPublishedPolicyByCodeUseCase,
        )

        country = resolve_company_policy_country(getattr(request.user, 'company', None))
        if not country:
            raise ValidationAppException(AppErrorCode.POLICY_INVALID_COUNTRY)
        result = GetPublishedPolicyByCodeUseCase(_repo(), _storage()).execute(code, country)
        return wrap_response(result.model_dump(mode='json'))


class ClientPolicyCountryContentView(APIView):
    """Lee el markdown de una política client activa."""

    permission_classes = [IsAuthenticated, IsCompanyMember]

    def get(self, request, pk, country, *args, **kwargs):
        result = GetClientPolicyCountryContentUseCase(_repo(), _storage()).execute(pk, country)
        return wrap_response(result.model_dump(mode='json'))


class ClientSignPolicyView(APIView):
    """Firma la versión publicada del país (audiencia client)."""

    permission_classes = [IsAuthenticated, IsCompanyMember]

    @validated_body(SignPolicyBody)
    def post(self, request, pk, *args, body: dict, **kwargs):
        from platform.features.compliance.policy.policy.application.country_resolve import (
            resolve_company_policy_country,
        )
        from platform.features.compliance.policy.policy.domain.schemas import normalize_country
        from core.errors import AppErrorCode, ValidationAppException

        company_country = resolve_company_policy_country(
            getattr(request.user, 'company', None),
        )
        if not company_country:
            raise ValidationAppException(AppErrorCode.POLICY_INVALID_COUNTRY)
        try:
            requested = normalize_country(body['country'])
        except ValueError as exc:
            raise ValidationAppException(AppErrorCode.POLICY_INVALID_COUNTRY) from exc
        if requested != company_country:
            raise ValidationAppException(AppErrorCode.POLICY_COUNTRY_MISMATCH)

        RequireActiveClientPolicyUseCase(_repo()).execute(pk)
        schema = SignPolicySchema(
            policy_id=pk,
            country=company_country,
            signatory=_client_signatory(request),
            context=_sign_context(request, channel=body.get('channel', 'web')),
        )
        result = SignPolicyUseCase(_repo(), _sig_repo(), _storage()).execute(schema)
        audit_log(
            request, 'PolicySignature', result.id, 'CREATE',
            f'Client policy signed: {result.policy_code}/{result.country}',
        )
        return wrap_response(
            result.model_dump(mode='json'),
            status_code=201,
            message='The policy has been signed successfully.',
        )


class ClientMyPolicySignaturesView(APIView):
    """Firmas del usuario actual sobre una política (auditoría propia)."""

    permission_classes = [IsAuthenticated, IsCompanyMember]

    @validated_query(PolicySignaturesQuery)
    def get(self, request, pk, *args, query: PaginatedQuery, **kwargs):
        RequireActiveClientPolicyUseCase(_repo()).execute(pk)
        filters = dict(query.filters or {})
        filters['subject_id'] = str(request.user.id)
        filters['subject_type'] = PolicySubjectType.CLIENT.value
        items = ListPolicySignaturesUseCase(_repo(), _sig_repo()).execute(pk, filters=filters)
        return _catalog_response(query, items)


class ClientVerifyPolicySignatureView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyMember]

    def get(self, request, signature_id, *args, **kwargs):
        from core.errors import AppErrorCode, NotFoundException

        row = _sig_repo().get_by_id(signature_id)
        if (
            not row
            or row.subject_type != PolicySubjectType.CLIENT
            or row.subject_id != str(request.user.id)
        ):
            raise NotFoundException(AppErrorCode.POLICY_SIGNATURE_NOT_FOUND)
        result = VerifyPolicySignatureUseCase(_sig_repo()).execute(signature_id)
        return wrap_response(result.model_dump(mode='json'))
