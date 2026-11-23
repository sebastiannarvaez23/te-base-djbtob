import uuid

from core.auth.cookie_authentication import CookieTokenAuthentication as TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.audit import audit_log, security_log
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, NotFoundException, PermissionException, ValidationAppException
from core.parameters import get_parameter
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication
from platform.features.company.tenant.company.application.close_company import (
    CloseCompanyUseCase,
    CompleteSelfCloseUseCase,
    ReopenCompanyUseCase,
    SelfCloseCompanyUseCase,
)
from platform.features.company.tenant.company.application.deregistration_policy import (
    RequireDeregistrationPolicySignatureUseCase,
)
from platform.features.company.tenant.company.application.export_company import (
    ExportClosedTenantUseCase,
    GetTenantExportDownloadUseCase,
)
from platform.features.company.tenant.company.application.legal_hold import SetLegalHoldUseCase
from platform.features.company.tenant.company.application.purge_company import PurgeClosedCompanyUseCase
from platform.features.company.tenant.company.application.use_cases import (
    GetCompanyDetailByIdUseCase,
    GetCompanyDetailByNitUseCase,
    CreateCompanyUseCase,
    ListCompaniesPaginatedUseCase,
    ToggleCompanyActiveUseCase,
    UpdateCompanySettingsUseCase,
)
from platform.features.company.tenant.company.domain.lifecycle import (
    CLOSE_GRACE_PARAM,
    DEFAULT_CLOSE_GRACE_DAYS,
    LIFECYCLE_GONE,
    SELF_CLOSE_ADMIN_ROLE,
)
from platform.features.company.tenant.company.domain.schemas import (
    CloseCompanySchema,
    CompleteSelfCloseSchema,
    CreateCompanySchema,
    ExportClosedTenantSchema,
    PurgeClosedCompanySchema,
    ReopenCompanySchema,
    SelfCloseCompanySchema,
    SetLegalHoldSchema,
    UpdateCompanySchema,
)
from platform.features.company.tenant.company.infrastructure.export_store import MinioTenantExportStore
from platform.features.company.tenant.company.infrastructure.offboarding import (
    DjangoCompanyOffboardingRepository,
    EmailCompanyCloseNotifier,
    RedisTenantSessionRevoker,
)
from platform.features.company.tenant.company.infrastructure.repositories import DjangoCompanyRepository
from platform.features.company.tenant.company.presentation.queries import CompanyQuery
from platform.features.company.tenant.company.presentation.bodies import (
    CloseCompanyBody,
    CompleteSelfCloseBody,
    CreateCompanyBody,
    ExportClosedTenantBody,
    LegalHoldBody,
    PurgeClosedCompanyBody,
    SelfCloseCompanyBody,
    UpdateCompanyBody,
)


class CompanyListCreateAPIView(APIView):
    """Paginated list + create — platform admin only."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(CompanyQuery)
    def get(self, request, *, query: PaginatedQuery):
        result = ListCompaniesPaginatedUseCase(DjangoCompanyRepository()).execute(query)
        return wrap_response({
            'items': [item.model_dump() for item in result.items],
            'total': result.total,
            'page': result.page,
            'page_size': result.page_size,
            'total_pages': result.total_pages,
        })

    @validated_body(CreateCompanyBody)
    def post(self, request, *, body: dict):
        vd = body

        schema = CreateCompanySchema(
            schema_name=vd['schema_name'],
            nit=vd['nit'],
            name=vd['name'],
            address=vd['address'],
            geo_city_id=vd['geo_city_id'],
            subscription_id=vd['subscription'],
            billing_interval=vd.get('billing_interval') or 'monthly',
        )
        result = CreateCompanyUseCase(DjangoCompanyRepository()).execute(schema)

        audit_log(request, 'Company', result.id, 'CREATE',
                  f'Company created: {schema.name} (nit={schema.nit}, schema={schema.schema_name})')
        return wrap_response(
            result.model_dump(mode='json'),
            status_code=201,
            message="The item has been created successfully.",
        )


class CompanyDetailAPIView(APIView):
    """Retrieve a single company by NIT."""

    authentication_classes = [AdminTokenAuthentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, nitcompany):
        if not nitcompany:
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail='NIT is required.',
            )
        company = GetCompanyDetailByNitUseCase(DjangoCompanyRepository()).execute(nitcompany)
        if not company:
            raise NotFoundException(AppErrorCode.COMPANY_NOT_FOUND)
        return wrap_response(company.model_dump(mode='json'))


def _assert_company_access(request, company_id: uuid.UUID) -> None:
    if isinstance(getattr(request, 'successful_authenticator', None), AdminTokenAuthentication):
        return
    user_company_id = getattr(request.user, 'company_id', None)
    if user_company_id is None or str(user_company_id) != str(company_id):
        raise NotFoundException(AppErrorCode.COMPANY_NOT_FOUND)


def _assert_company_administrator(request, company_id: uuid.UUID) -> None:
    _assert_company_access(request, company_id)
    role_name = getattr(getattr(request.user, 'rol', None), 'name', None)
    if role_name != SELF_CLOSE_ADMIN_ROLE:
        raise PermissionException(AppErrorCode.PERM_INSUFFICIENT)


def _close_grace_days() -> int:
    grace = get_parameter(CLOSE_GRACE_PARAM, default=DEFAULT_CLOSE_GRACE_DAYS)
    try:
        return int(grace)
    except (TypeError, ValueError):
        return DEFAULT_CLOSE_GRACE_DAYS


class CompanyByIdAPIView(APIView):
    """Retrieve or update a company by id (client settings; empty NIT supported)."""

    authentication_classes = [AdminTokenAuthentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, company_id: uuid.UUID):
        _assert_company_access(request, company_id)
        company = GetCompanyDetailByIdUseCase(DjangoCompanyRepository()).execute(company_id)
        if not company:
            raise NotFoundException(AppErrorCode.COMPANY_NOT_FOUND)
        return wrap_response(company.model_dump(mode='json'))

    @validated_body(UpdateCompanyBody)
    def patch(self, request, company_id: uuid.UUID, *, body: dict):
        _assert_company_access(request, company_id)
        schema = UpdateCompanySchema(**body)
        company = UpdateCompanySettingsUseCase(DjangoCompanyRepository()).execute(company_id, schema)
        if not company:
            raise NotFoundException(AppErrorCode.COMPANY_NOT_FOUND)
        audit_log(request, 'Company', company_id, 'UPDATE', changes=body)
        return wrap_response(company.model_dump(mode='json'))


class CompanySelfCloseAPIView(APIView):
    """Tenant administrator closes their own company from client settings."""

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(SelfCloseCompanyBody)
    def post(self, request, company_id: uuid.UUID, *, body: dict):
        _assert_company_administrator(request, company_id)
        actor_id = _actor_admin_id(request)
        if actor_id is None:
            raise PermissionException(AppErrorCode.PERM_INSUFFICIENT)
        from platform.features.compliance.policy.policy.application.country_resolve import (
            resolve_company_policy_country,
        )
        from platform.features.compliance.policy.policy.infrastructure.repositories import (
            DjangoPolicyRepository,
            DjangoPolicySignatureRepository,
        )

        result = SelfCloseCompanyUseCase(
            _offboarding(),
            RedisTenantSessionRevoker(),
            EmailCompanyCloseNotifier(),
            _export_store(),
            policy_gate=RequireDeregistrationPolicySignatureUseCase(
                DjangoPolicyRepository(),
                DjangoPolicySignatureRepository(),
            ),
        ).execute(SelfCloseCompanySchema(
            company_id=company_id,
            confirmation=body['confirmation'],
            actor_user_id=actor_id,
            grace_days=_close_grace_days(),
            accepted=bool(body.get('accepted')),
            country=resolve_company_policy_country(getattr(request.user, 'company', None)),
        ))
        audit_log(
            request, 'Company', company_id, 'CLOSE',
            f'Company self-closed: {result.name}',
            changes={'lifecycle': result.lifecycle, 'purge_after': result.purge_after},
        )
        security_log(
            request,
            event_type='COMPANY_CLOSED',
            resource=str(company_id),
            detail=result.closed_reason,
        )
        if result.lifecycle == LIFECYCLE_GONE:
            security_log(
                request,
                event_type='COMPANY_PURGED',
                resource=str(company_id),
            )
        return wrap_response(result.model_dump(mode='json'), message='Company closed')


class CompanySelfCloseCompleteAPIView(APIView):
    """Persist churn reason and finish the acting administrator session."""

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(CompleteSelfCloseBody)
    def post(self, request, company_id: uuid.UUID, *, body: dict):
        _assert_company_administrator(request, company_id)
        actor_id = _actor_admin_id(request)
        if actor_id is None:
            raise PermissionException(AppErrorCode.PERM_INSUFFICIENT)
        result = CompleteSelfCloseUseCase(
            _offboarding(),
            RedisTenantSessionRevoker(),
            _export_store(),
        ).execute(CompleteSelfCloseSchema(
            company_id=company_id,
            actor_user_id=actor_id,
            reason=body.get('reason') or '',
        ))
        audit_log(
            request, 'Company', company_id, 'CLOSE_REASON',
            f'Company close completed: {result.name}',
            changes={'lifecycle': result.lifecycle, 'closed_reason': result.closed_reason},
        )
        if result.lifecycle == LIFECYCLE_GONE:
            security_log(
                request,
                event_type='COMPANY_PURGED',
                resource=str(company_id),
            )
        return wrap_response(result.model_dump(mode='json'), message='Company close completed')


class CompanyToggleActiveAPIView(APIView):
    """Toggle active/suspended status for a company's latest subscription."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, company_id: uuid.UUID):
        company = ToggleCompanyActiveUseCase(DjangoCompanyRepository()).execute(company_id)
        if not company:
            raise NotFoundException(AppErrorCode.COMPANY_NOT_FOUND)
        audit_log(request, 'Company', company_id, 'TOGGLE_ACTIVE', f'is_active={company.is_active}')
        return wrap_response(company.model_dump())


def _actor_admin_id(request):
    raw = getattr(request.user, 'id', None)
    if raw in (None, ''):
        return None
    return uuid.UUID(str(raw))


def _offboarding():
    return DjangoCompanyOffboardingRepository()


class CompanyCloseAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(CloseCompanyBody)
    def post(self, request, company_id: uuid.UUID, *, body: dict):
        grace_days = _close_grace_days()
        result = CloseCompanyUseCase(
            _offboarding(),
            RedisTenantSessionRevoker(),
            EmailCompanyCloseNotifier(),
            _export_store(),
        ).execute(CloseCompanySchema(
            company_id=company_id,
            reason=body['reason'],
            actor_admin_id=_actor_admin_id(request),
            grace_days=grace_days,
        ))
        audit_log(
            request, 'Company', company_id, 'CLOSE',
            f'Company closed: {result.name}',
            changes={'lifecycle': result.lifecycle, 'purge_after': result.purge_after},
        )
        security_log(
            request,
            event_type='COMPANY_CLOSED',
            resource=str(company_id),
            detail=result.closed_reason,
        )
        if result.lifecycle == LIFECYCLE_GONE:
            audit_log(
                request, 'Company', company_id, 'PURGE',
                f'Company purged: {result.name}',
                changes={'lifecycle': result.lifecycle},
            )
            security_log(
                request,
                event_type='COMPANY_PURGED',
                resource=str(company_id),
            )
            return wrap_response(
                result.model_dump(mode='json'),
                message='Company closed and purged',
            )
        return wrap_response(result.model_dump(mode='json'), message='Company closed')


class CompanyReopenAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, company_id: uuid.UUID):
        result = ReopenCompanyUseCase(_offboarding()).execute(
            ReopenCompanySchema(
                company_id=company_id,
                actor_admin_id=_actor_admin_id(request),
            ),
        )
        audit_log(
            request, 'Company', company_id, 'REOPEN',
            f'Company reopened: {result.name}',
            changes={'lifecycle': result.lifecycle},
        )
        security_log(
            request,
            event_type='COMPANY_REOPENED',
            resource=str(company_id),
        )
        return wrap_response(result.model_dump(mode='json'), message='Company reopened')


def _export_store():
    return MinioTenantExportStore()


class CompanyLegalHoldAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(LegalHoldBody)
    def post(self, request, company_id: uuid.UUID, *, body: dict):
        result = SetLegalHoldUseCase(_offboarding()).execute(
            SetLegalHoldSchema(
                company_id=company_id,
                enabled=body['enabled'],
                reason=body.get('reason') or '',
                actor_admin_id=_actor_admin_id(request),
            ),
        )
        audit_log(
            request, 'Company', company_id, 'LEGAL_HOLD',
            f'legal_hold={result.legal_hold}',
            changes={'legal_hold': result.legal_hold, 'reason': result.legal_hold_reason},
        )
        security_log(
            request,
            event_type='COMPANY_LEGAL_HOLD',
            resource=str(company_id),
            detail=result.legal_hold_reason,
        )
        return wrap_response(result.model_dump(mode='json'), message='Legal hold updated')


class CompanyExportAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, company_id: uuid.UUID):
        result = GetTenantExportDownloadUseCase(_offboarding(), _export_store()).execute(company_id)
        return wrap_response(result.model_dump(mode='json'))

    @validated_body(ExportClosedTenantBody)
    def post(self, request, company_id: uuid.UUID, *, body: dict):
        result = ExportClosedTenantUseCase(_offboarding(), _export_store()).execute(
            ExportClosedTenantSchema(
                company_id=company_id,
                waived=bool(body.get('waived')),
                reason=body.get('reason') or '',
                actor_admin_id=_actor_admin_id(request),
            ),
        )
        audit_log(
            request, 'Company', company_id, 'EXPORT',
            'Export waived' if body.get('waived') else 'Tenant export attested',
            changes={'export_attested_at': result.export_attested_at},
        )
        return wrap_response(result.model_dump(mode='json'), message='Export attested')


class CompanyPurgeAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(PurgeClosedCompanyBody)
    def post(self, request, company_id: uuid.UUID, *, body: dict):
        result = PurgeClosedCompanyUseCase(_offboarding(), _export_store()).execute(
            PurgeClosedCompanySchema(
                company_id=company_id,
                force=bool(body.get('force')),
                reason=body.get('reason') or '',
                actor_admin_id=_actor_admin_id(request),
            ),
        )
        audit_log(
            request, 'Company', company_id, 'PURGE',
            f'Company purged: {result.name}',
            changes={'lifecycle': result.lifecycle},
        )
        security_log(
            request,
            event_type='COMPANY_PURGED',
            resource=str(company_id),
        )
        return wrap_response(result.model_dump(mode='json'), message='Company purged')
