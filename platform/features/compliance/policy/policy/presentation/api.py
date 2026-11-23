"""API admin de políticas de cumplimiento."""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.query import PaginatedQuery, validated_query
from core.storage import MinioStorageService
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication
from platform.features.compliance.policy.policy.application.sign_use_cases import (
    ListPendingPoliciesUseCase,
    ListPolicySignaturesUseCase,
    SignPolicyUseCase,
    VerifyPolicySignatureUseCase,
)
from platform.features.compliance.policy.policy.application.use_cases import (
    CreatePolicyUseCase,
    DeletePolicyCountryUseCase,
    DeletePolicyUseCase,
    DiscardPolicyCountryDraftUseCase,
    GetPolicyByIdUseCase,
    GetPolicyCountryContentUseCase,
    ListPoliciesUseCase,
    ListPolicyCountryVersionsUseCase,
    ReleasePolicyCountryDraftUseCase,
    SavePolicyCountryDraftUseCase,
    StartPolicyCountryDraftUseCase,
    UpdatePolicyUseCase,
)
from platform.features.compliance.policy.policy.domain.enums import PolicyAudience, PolicySubjectType
from platform.features.compliance.policy.policy.domain.schemas import (
    CreatePolicySchema,
    ReleasePolicyCountryDraftSchema,
    SavePolicyCountryDraftSchema,
    SignPolicyContextSchema,
    SignPolicySchema,
    SignatoryRef,
    UpdatePolicySchema,
)
from platform.features.compliance.policy.policy.infrastructure.repositories import DjangoPolicyRepository
from platform.features.compliance.policy.policy.presentation.bodies import (
    CreatePolicyBody,
    ReleasePolicyCountryDraftBody,
    SavePolicyCountryDraftBody,
    SignPolicyBody,
    UpdatePolicyBody,
)
from platform.features.compliance.policy.policy.presentation.queries import (
    PendingPoliciesQuery,
    PolicyCountryContentQuery,
    PolicyListQuery,
    PolicySignaturesQuery,
)


def _repo():
    return DjangoPolicyRepository()


def _storage():
    return MinioStorageService()


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


class PolicyListCreateView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(PolicyListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        items = ListPoliciesUseCase(_repo()).execute(filters=query.filters)
        return _catalog_response(query, items)

    @validated_body(CreatePolicyBody)
    def post(self, request, *args, body: dict, **kwargs):
        schema = CreatePolicySchema(
            code=body['code'],
            name=body['name'],
            audience=PolicyAudience(body['audience']),
            description=body.get('description', ''),
            is_active=body.get('is_active', True),
        )
        result = CreatePolicyUseCase(_repo()).execute(schema)
        audit_log(
            request, 'Policy', result.id, 'CREATE',
            f'Policy created: {result.code} ({result.audience.value})',
        )
        return wrap_response(
            result.model_dump(mode='json'),
            status_code=201,
            message='The policy has been created successfully.',
        )


class PolicyDetailView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        result = GetPolicyByIdUseCase(_repo()).execute(pk)
        return wrap_response(result.model_dump(mode='json'))

    @validated_body(UpdatePolicyBody)
    def patch(self, request, pk, *args, body: dict, **kwargs):
        schema = UpdatePolicySchema(**body)
        result = UpdatePolicyUseCase(_repo()).execute(pk, schema)
        audit_log(request, 'Policy', pk, 'UPDATE', changes=body)
        return wrap_response(result.model_dump(mode='json'))

    def delete(self, request, pk, *args, **kwargs):
        DeletePolicyUseCase(_repo(), _storage()).execute(pk)
        audit_log(request, 'Policy', pk, 'DELETE')
        return Response(status=status.HTTP_204_NO_CONTENT)


class PolicyCountryDraftView(APIView):
    """POST start/reopen · PUT save · DELETE discard."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, country, *args, **kwargs):
        result = StartPolicyCountryDraftUseCase(_repo(), _storage()).execute(pk, country)
        audit_log(
            request, 'PolicyCountryDraft', result.country, 'CREATE',
            f'Draft started: {pk}/{country}',
        )
        return wrap_response(result.model_dump(mode='json'), status_code=201)

    @validated_body(SavePolicyCountryDraftBody)
    def put(self, request, pk, country, *args, body: dict, **kwargs):
        schema = SavePolicyCountryDraftSchema(**body)
        result = SavePolicyCountryDraftUseCase(_repo(), _storage()).execute(pk, country, schema)
        audit_log(request, 'PolicyCountryDraft', result.id, 'UPDATE', f'Draft saved: {pk}/{country}')
        return wrap_response(result.model_dump(mode='json'))

    def delete(self, request, pk, country, *args, **kwargs):
        DiscardPolicyCountryDraftUseCase(_repo(), _storage()).execute(pk, country)
        audit_log(request, 'PolicyCountryDraft', pk, 'DELETE', f'country={country}')
        return Response(status=status.HTTP_204_NO_CONTENT)


class PolicyCountryDraftReleaseView(APIView):
    """Orquesta Approve → Release en un solo endpoint de UI."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(ReleasePolicyCountryDraftBody)
    def post(self, request, pk, country, *args, body: dict, **kwargs):
        schema = ReleasePolicyCountryDraftSchema(**body)
        result = ReleasePolicyCountryDraftUseCase(_repo(), _storage()).execute(pk, country, schema)
        audit_log(
            request, 'PolicyCountry', result.country.id, 'RELEASE',
            (
                f'Draft approved+released: {pk}/{country} '
                f'v{result.country.version} revoked={result.revoked_version}'
            ),
        )
        return wrap_response(result.model_dump(mode='json'))


class PolicyCountryVersionsView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, country, *args, **kwargs):
        items = ListPolicyCountryVersionsUseCase(_repo()).execute(pk, country)
        return wrap_response([item.model_dump(mode='json') for item in items])


class PolicyCountryDetailView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(PolicyCountryContentQuery)
    def get(self, request, pk, country, *args, query: PaginatedQuery, **kwargs):
        status_filter = (query.filters or {}).get('status')
        result = GetPolicyCountryContentUseCase(_repo(), _storage()).execute(
            pk, country, status=status_filter,
        )
        return wrap_response(result.model_dump(mode='json'))

    def delete(self, request, pk, country, *args, **kwargs):
        DeletePolicyCountryUseCase(_repo(), _storage()).execute(pk, country)
        audit_log(request, 'PolicyCountry', pk, 'DELETE', f'country={country}')
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Firmas digitales ──────────────────────────────────────────────────────────


def _sig_repo():
    from platform.features.compliance.policy.policy.infrastructure.repositories import (
        DjangoPolicySignatureRepository,
    )
    return DjangoPolicySignatureRepository()


def _admin_signatory(request) -> SignatoryRef:
    return SignatoryRef(
        subject_type=PolicySubjectType.ADMIN,
        subject_id=str(request.user.id),
        tenant_id=None,
    )


def _sign_context(request, *, channel: str = 'web') -> SignPolicyContextSchema:
    return SignPolicyContextSchema(
        ip_address=request.META.get('REMOTE_ADDR') or None,
        user_agent=request.META.get('HTTP_USER_AGENT') or None,
        request_id=getattr(request, 'request_id', None),
        channel=channel or 'web',
    )


class PendingPoliciesView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(PendingPoliciesQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        country = (query.filters or {}).get('country') or 'CO'
        items = ListPendingPoliciesUseCase(_sig_repo()).execute(
            subject=_admin_signatory(request),
            country=country,
        )
        return _catalog_response(query, items)


class SignPolicyView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(SignPolicyBody)
    def post(self, request, pk, *args, body: dict, **kwargs):
        schema = SignPolicySchema(
            policy_id=pk,
            country=body['country'],
            signatory=_admin_signatory(request),
            context=_sign_context(request, channel=body.get('channel', 'web')),
        )
        result = SignPolicyUseCase(_repo(), _sig_repo(), _storage()).execute(schema)
        audit_log(
            request, 'PolicySignature', result.id, 'CREATE',
            f'Policy signed: {result.policy_code}/{result.country}',
        )
        return wrap_response(
            result.model_dump(mode='json'),
            status_code=201,
            message='The policy has been signed successfully.',
        )


class PolicySignaturesListView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(PolicySignaturesQuery)
    def get(self, request, pk, *args, query: PaginatedQuery, **kwargs):
        items = ListPolicySignaturesUseCase(_repo(), _sig_repo()).execute(
            pk, filters=query.filters,
        )
        return _catalog_response(query, items)


class VerifyPolicySignatureView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, signature_id, *args, **kwargs):
        result = VerifyPolicySignatureUseCase(_sig_repo()).execute(signature_id)
        return wrap_response(result.model_dump(mode='json'))
