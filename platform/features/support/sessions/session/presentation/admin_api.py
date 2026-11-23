"""Platform admin API for live support sessions."""

from uuid import UUID

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.decorators.response import wrap_response
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication
from platform.features.support.sessions.session.application import factory as session_factory
from core.audit import audit_log
from platform.features.support.sessions.session.domain.schemas import (
    AcceptSupportSessionSchema,
    SendSupportMessageSchema,
    SupportSessionListFilters,
    UpdateSupportSettingsSchema,
)
from platform.features.support.sessions.session.presentation.bodies import (
    SendSupportMessageBody,
    UpdateSupportSettingsBody,
)
from platform.features.support.sessions.session.presentation.queries import (
    SupportSessionEventsQuery,
    SupportSessionListQuery,
    SupportSessionMessagesQuery,
)


def _admin_label(user) -> str:
    first = getattr(user, 'first_name', '') or ''
    last = getattr(user, 'last_name', '') or ''
    full = f'{first} {last}'.strip()
    return full or (getattr(user, 'username', '') or getattr(user, 'email', '') or 'Agent')


class AdminActiveSupportSessionView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        session = session_factory.build_get_active_agent().execute(request.user.pk)
        if session is None:
            return wrap_response(None, message='No active support session')
        return wrap_response(session.model_dump(mode='json'), message='OK')


class AdminSupportSessionListView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(SupportSessionListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        f = query.filters
        items, total = session_factory.build_list().execute(
            SupportSessionListFilters(
                status=f.get('status') or None,
                company=f.get('company') or None,
                search=f.get('search') or None,
                from_date=f.get('from'),
                to_date=f.get('to'),
            ),
            limit=query.limit,
            offset=query.offset,
        )
        return wrap_response({
            'items': [i.model_dump(mode='json') for i in items],
            'total': total,
            'page': query.page,
            'page_size': query.page_size,
            'total_pages': (total + query.page_size - 1) // query.page_size if query.page_size else 0,
        })


class AdminSupportSessionDetailView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id: UUID, *args, **kwargs):
        session = session_factory.build_get().execute(session_id)
        return wrap_response(session.model_dump(mode='json'), message='OK')


class AdminSupportSessionAcceptView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id: UUID, *args, **kwargs):
        session = session_factory.build_accept().execute(
            session_id,
            AcceptSupportSessionSchema(
                admin_user_id=request.user.pk,
                admin_label=_admin_label(request.user),
            ),
        )
        return wrap_response(session.model_dump(mode='json'), message='Support session accepted')


class AdminSupportSessionMessagesView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(SupportSessionMessagesQuery)
    def get(self, request, session_id: UUID, *args, query: PaginatedQuery, **kwargs):
        items, total = session_factory.build_list_messages().execute(
            session_id,
            limit=query.limit,
            offset=query.offset,
        )
        return wrap_response({
            'items': [i.model_dump(mode='json') for i in items],
            'total': total,
            'page': query.page,
            'page_size': query.page_size,
            'total_pages': (total + query.page_size - 1) // query.page_size if query.page_size else 0,
        })

    @validated_body(SendSupportMessageBody)
    def post(self, request, session_id: UUID, *args, body: dict, **kwargs):
        message = session_factory.build_send_agent().execute(
            session_id,
            admin_user_id=request.user.pk,
            data=SendSupportMessageSchema(body=body['body']),
        )
        return wrap_response(
            message.model_dump(mode='json'),
            status_code=201,
            message='Message sent',
        )


class AdminSupportSessionEventsView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(SupportSessionEventsQuery)
    def get(self, request, session_id: UUID, *args, query: PaginatedQuery, **kwargs):
        items, total = session_factory.build_list_events().execute(
            session_id,
            limit=query.limit,
            offset=query.offset,
        )
        return wrap_response({
            'items': [i.model_dump(mode='json') for i in items],
            'total': total,
            'page': query.page,
            'page_size': query.page_size,
            'total_pages': (total + query.page_size - 1) // query.page_size if query.page_size else 0,
        })


class AdminSupportSessionReadView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id: UUID, *args, **kwargs):
        session = session_factory.build_mark_agent_read().execute(
            session_id,
            admin_user_id=request.user.pk,
        )
        return wrap_response(session.model_dump(mode='json'), message='Marked as read')


class AdminSupportSessionCloseView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id: UUID, *args, **kwargs):
        session = session_factory.build_close().execute(
            session_id,
            admin_user_id=request.user.pk,
        )
        return wrap_response(session.model_dump(mode='json'), message='Support session closed')


class AdminSupportSettingsView(APIView):
    """``GET/PATCH /api/v1/platform/support/settings/``."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        result = session_factory.build_get_settings().execute()
        return wrap_response(result.model_dump(mode='json'))

    @validated_body(UpdateSupportSettingsBody)
    def patch(self, request, *args, body: dict, **kwargs):
        from core.errors.codes import AppErrorCode
        from core.errors.exceptions import ValidationAppException
        from pydantic import ValidationError

        try:
            patch = UpdateSupportSettingsSchema(**body)
        except ValidationError as exc:
            raise ValidationAppException(AppErrorCode.VALIDATION_ERROR) from exc
        result = session_factory.build_update_settings().execute(patch)
        audit_log(
            request,
            'SupportSettings',
            'default',
            'UPDATE',
            changes=body,
        )
        return wrap_response(result.model_dump(mode='json'))
