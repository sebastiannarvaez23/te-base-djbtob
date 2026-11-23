from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.permissions import IsCompanyMember
from core.validators import validated_body

from ..infrastructure.factory import build_create, build_evaluate, build_get_current
from .bodies import CreateRefundBody, RefundPreviewBody


def _company_id(request):
    """Prefer the JWT company so these views work on the public URLconf too."""
    user = getattr(request, 'user', None)
    company_id = getattr(user, 'company_id', None) if user is not None else None
    if company_id:
        return company_id
    return request.tenant.id


def _schema_name(request) -> str:
    company = getattr(getattr(request, 'user', None), 'company', None)
    if company is not None and getattr(company, 'schema_name', None):
        return company.schema_name
    tenant = getattr(request, 'tenant', None)
    return getattr(tenant, 'schema_name', '') or ''


class RefundEligibilityView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyMember]

    def get(self, request, *args, **kwargs):
        result = build_evaluate().eligibility(_company_id(request))
        return wrap_response(result.model_dump(mode='json'))


class RefundPreviewView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyMember]

    @validated_body(RefundPreviewBody)
    def post(self, request, *args, body: dict, **kwargs):
        result = build_evaluate().preview(
            _company_id(request), body['target_subscription_id'],
        )
        return wrap_response(result.model_dump(mode='json'))


class RefundRequestView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyMember]

    @validated_body(CreateRefundBody)
    def post(self, request, *args, body: dict, **kwargs):
        user_id = getattr(getattr(request, 'user', None), 'id', None)
        ticket = build_create().execute(
            company_id=_company_id(request),
            target_subscription_id=body['target_subscription_id'],
            schema_name=_schema_name(request),
            requested_by_id=user_id,
        )
        audit_log(
            request, 'RefundRequest', ticket.id, 'CREATE',
            f'Refund {ticket.ticket_number} to {ticket.to_subscription_name}',
        )
        return wrap_response(ticket.model_dump(mode='json'), status_code=201)


class CurrentRefundView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyMember]

    def get(self, request, *args, **kwargs):
        ticket = build_get_current().execute(_company_id(request))
        if ticket is None:
            return wrap_response(None)
        return wrap_response(ticket.model_dump(mode='json'))
