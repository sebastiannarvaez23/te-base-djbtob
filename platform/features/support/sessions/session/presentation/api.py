"""Client (tenant) API for live support sessions."""

from uuid import UUID

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.auth.cookie_authentication import JWTAccessAuthentication
from core.decorators.response import wrap_response
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.features.support.sessions.session.application import factory as session_factory
from platform.features.support.sessions.session.domain.schemas import (
    CreateSupportSessionSchema,
    RateSupportSessionSchema,
    SendSupportMessageSchema,
)
from platform.features.support.sessions.session.presentation.bodies import (
    CreateSupportSessionBody,
    RateSupportSessionBody,
    SendSupportMessageBody,
)
from platform.features.support.sessions.session.presentation.queries import (
    SupportSessionMessagesQuery,
)


def _requester_display_name(user) -> str:
    first = getattr(user, 'first_name', '') or ''
    last = getattr(user, 'last_name', '') or ''
    full = f'{first} {last}'.strip()
    return full or (getattr(user, 'username', '') or '')


def _company_name(user) -> str:
    company = getattr(user, 'company', None)
    if company is None:
        return ''
    return getattr(company, 'name', '') or ''


def _company_context(request) -> tuple[str, str]:
    """Resolve company id + schema from JWT user (SPA host uses public URLconf)."""
    company = getattr(request.user, 'company', None)
    company_id = str(getattr(company, 'id', '') or '')
    schema_name = getattr(company, 'schema_name', None) or ''
    if not schema_name:
        tenant = getattr(request, 'tenant', None)
        tenant_schema = getattr(tenant, 'schema_name', '') or ''
        if tenant_schema and tenant_schema != 'public':
            schema_name = tenant_schema
    return company_id, schema_name


class ClientActiveSupportSessionView(APIView):
    authentication_classes = [JWTAccessAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        session = session_factory.build_get_active_client().execute(request.user.pk)
        if session is None:
            return wrap_response(None, message='No active support session')
        return wrap_response(session.model_dump(mode='json'), message='OK')


class ClientCreateSupportSessionView(APIView):
    authentication_classes = [JWTAccessAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(CreateSupportSessionBody)
    def post(self, request, *args, body: dict, **kwargs):
        from core.errors.codes import AppErrorCode
        from core.errors.exceptions import ValidationAppException

        company_id, schema_name = _company_context(request)
        if not company_id or not schema_name:
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail='Company membership is required to open a support session.',
            )
        session = session_factory.build_create().execute(
            CreateSupportSessionSchema(
                motive=body['motive'],
                company_id=company_id,
                schema_name=schema_name,
                company_name=_company_name(request.user),
                requester_user_id=request.user.pk,
                requester_username=getattr(request.user, 'username', '') or '',
                requester_display_name=_requester_display_name(request.user),
            )
        )
        return wrap_response(
            session.model_dump(mode='json'),
            status_code=201,
            message='Support session created',
        )


class ClientSupportSessionMessagesView(APIView):
    authentication_classes = [JWTAccessAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(SupportSessionMessagesQuery)
    def get(self, request, session_id: UUID, *args, query: PaginatedQuery, **kwargs):
        active = session_factory.build_get_active_client().execute(request.user.pk)
        items, total = session_factory.build_list_messages().execute(
            session_id,
            limit=query.limit,
            offset=query.offset,
            requester_user_id=request.user.pk,
        )
        return wrap_response({
            'items': [i.model_dump(mode='json') for i in items],
            'total': total,
            'page': query.page,
            'page_size': query.page_size,
            'total_pages': (total + query.page_size - 1) // query.page_size if query.page_size else 0,
            'active_session_id': str(active.id) if active else None,
        })

    @validated_body(SendSupportMessageBody)
    def post(self, request, session_id: UUID, *args, body: dict, **kwargs):
        message = session_factory.build_send_client().execute(
            session_id,
            requester_user_id=request.user.pk,
            data=SendSupportMessageSchema(body=body['body']),
        )
        return wrap_response(
            message.model_dump(mode='json'),
            status_code=201,
            message='Message sent',
        )


class ClientSupportSessionReadView(APIView):
    authentication_classes = [JWTAccessAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id: UUID, *args, **kwargs):
        session = session_factory.build_mark_client_read().execute(
            session_id,
            requester_user_id=request.user.pk,
        )
        return wrap_response(session.model_dump(mode='json'), message='Marked as read')


class ClientSupportSessionCancelView(APIView):
    authentication_classes = [JWTAccessAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id: UUID, *args, **kwargs):
        session = session_factory.build_cancel().execute(
            session_id,
            requester_user_id=request.user.pk,
        )
        return wrap_response(session.model_dump(mode='json'), message='Support session cancelled')


class ClientSupportSessionRatingView(APIView):
    authentication_classes = [JWTAccessAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(RateSupportSessionBody)
    def post(self, request, session_id: UUID, *args, body: dict, **kwargs):
        session = session_factory.build_rate().execute(
            session_id,
            requester_user_id=request.user.pk,
            data=RateSupportSessionSchema(
                rating=body['rating'],
                comment=body.get('comment') or '',
            ),
        )
        return wrap_response(session.model_dump(mode='json'), message='Support session rated')


class ClientSupportSettingsView(APIView):
    """``GET /api/v1/support/settings/`` — queue timeout + alternate channels."""

    authentication_classes = [JWTAccessAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        result = session_factory.build_get_settings().execute()
        return wrap_response(result.model_dump(mode='json'))
