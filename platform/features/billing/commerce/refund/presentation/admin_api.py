"""Admin endpoints for refund tickets (public schema, AdminTokenAuthentication)."""
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication

from ..infrastructure.factory import (
    build_approve,
    build_get_admin,
    build_list,
    build_reject,
)
from .bodies import RejectRefundBody
from .queries import AdminRefundQuery


class AdminRefundListView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(AdminRefundQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        result = build_list().execute(query)
        return wrap_response({
            'items': [item.model_dump(mode='json') for item in result.items],
            'total': result.total,
            'page': result.page,
            'page_size': result.page_size,
            'total_pages': result.total_pages,
        })


class AdminRefundDetailView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, ticket_id, *args, **kwargs):
        ticket = build_get_admin().execute(ticket_id)
        return wrap_response(ticket.model_dump(mode='json'))


class AdminRefundApproveView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, ticket_id, *args, **kwargs):
        user_id = getattr(getattr(request, 'user', None), 'id', None)
        ticket = build_approve().execute(ticket_id, approved_by_id=user_id)
        audit_log(
            request, 'RefundRequest', ticket.id, 'APPROVE',
            f'Approved {ticket.ticket_number} → {ticket.to_subscription_name}',
        )
        return wrap_response(ticket.model_dump(mode='json'))


class AdminRefundRejectView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(RejectRefundBody)
    def post(self, request, ticket_id, *args, body: dict, **kwargs):
        ticket = build_reject().execute(ticket_id, reason=body.get('reason') or '')
        audit_log(
            request, 'RefundRequest', ticket.id, 'REJECT',
            f'Rejected {ticket.ticket_number}',
        )
        return wrap_response(ticket.model_dump(mode='json'))
