import uuid

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.audit import security_log
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, NotFoundException
from core.query import PaginatedQuery, validated_query
from platform.core.authentication import AdminTokenAuthentication
from platform.features.security.identity.sessions.application.use_cases import (
    KillAllSessionsUseCase,
    KillSessionsByCompanyUseCase,
    KillSessionsByUserUseCase,
    KillSessionUseCase,
    ListSessionsPaginatedUseCase,
)
from platform.features.security.identity.sessions.infrastructure.repositories import DjangoSessionRepository
from platform.features.security.identity.sessions.presentation.queries import SessionsQuery


class SessionListAPIView(APIView):
    """Paginated list of active sessions (admin + client tokens) — platform admin only."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(SessionsQuery)
    def get(self, request, *, query: PaginatedQuery):
        result = ListSessionsPaginatedUseCase(DjangoSessionRepository()).execute(query)
        return wrap_response({
            'items': [item.model_dump(mode='json') for item in result.items],
            'total': result.total,
            'page': result.page,
            'page_size': result.page_size,
            'total_pages': result.total_pages,
        })


class SessionKillAPIView(APIView):
    """Kill a single session by its token key."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, session_id: str):
        deleted = KillSessionUseCase(DjangoSessionRepository()).execute(session_id)
        if not deleted:
            raise NotFoundException(AppErrorCode.SESSION_NOT_FOUND)

        security_log(
            request,
            event_type='SESSION_KILLED',
            resource=f'/api/v1/platform/sessions/{session_id}/',
            detail=f'session_id={session_id}',
        )
        return wrap_response({'detail': 'Session terminated.'})


class SessionKillByUserAPIView(APIView):
    """Kill all sessions for a specific user."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, user_id: uuid.UUID):
        count = KillSessionsByUserUseCase(DjangoSessionRepository()).execute(user_id)
        security_log(
            request,
            event_type='SESSIONS_KILLED_BY_USER',
            target_user_id=user_id,
            resource=f'/api/v1/platform/sessions/by-user/{user_id}/',
            detail=f'sessions_killed={count}',
        )
        return wrap_response({'detail': f'{count} session(s) terminated.', 'count': count})


class SessionKillByCompanyAPIView(APIView):
    """Kill all sessions for all users of a given company."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, company_id: uuid.UUID):
        count = KillSessionsByCompanyUseCase(DjangoSessionRepository()).execute(company_id)
        security_log(
            request,
            event_type='SESSIONS_KILLED_BY_COMPANY',
            resource=f'/api/v1/platform/sessions/by-company/{company_id}/',
            detail=f'company_id={company_id} sessions_killed={count}',
        )
        return wrap_response({'detail': f'{count} session(s) terminated.', 'count': count})


class SessionKillAllAPIView(APIView):
    """Kill ALL sessions across all companies and admin users."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        count = KillAllSessionsUseCase(DjangoSessionRepository()).execute()
        security_log(
            request,
            event_type='ALL_SESSIONS_KILLED',
            resource='/api/v1/platform/sessions/all/',
            detail=f'sessions_killed={count}',
        )
        return wrap_response({'detail': f'{count} session(s) terminated.', 'count': count})
