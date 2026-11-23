"""API del assistant."""

from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.access.decorators import track_usage
from core.decorators.response import wrap_response
from core.permissions import HasSubscriptionAccess, IsCompanyMember
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body

from client.features.communication.assistant.chat.domain.constants import ASSISTANT_CHAT_FEATURE
from client.features.communication.assistant.chat.application.use_cases import (
    ChatTurnUseCase,
    GetAssistantStatusUseCase,
    GetConversationMessagesUseCase,
    ListConversationsUseCase,
    RenameConversationUseCase,
)
from client.features.communication.assistant.chat.infrastructure.repositories import (
    DjangoAssistantConversationRepository,
)
from client.features.communication.assistant.chat.presentation.bodies import ChatTurnBody, RenameConversationBody
from client.features.communication.assistant.chat.presentation.queries import AssistantConversationListQuery
from client.features.communication.assistant.chat.presentation.runtime import load_chat_runtime


def _repo():
    return DjangoAssistantConversationRepository()


_ASSISTANT_PERMISSIONS = [IsAuthenticated, IsCompanyMember, HasSubscriptionAccess]


class AssistantStatusView(APIView):
    permission_classes = _ASSISTANT_PERMISSIONS
    subscription_functionality = ASSISTANT_CHAT_FEATURE
    subscription_check_quota = False

    def get(self, request, *args, **kwargs):
        policy, _registry = load_chat_runtime()
        status = GetAssistantStatusUseCase(policy).execute()
        return wrap_response(status.model_dump())


class AssistantChatView(APIView):
    permission_classes = _ASSISTANT_PERMISSIONS
    subscription_functionality = ASSISTANT_CHAT_FEATURE

    @track_usage(ASSISTANT_CHAT_FEATURE)
    @validated_body(ChatTurnBody)
    def post(self, request, *args, body: dict, **kwargs):
        from django.db import connection

        from client.features.communication.assistant.chat.infrastructure.run_repository import (
            DjangoAssistantAgentRunRepository,
        )
        from client.features.communication.assistant.credentials.infrastructure.repositories import (
            DjangoAssistantCredentialRepository,
        )

        policy, registry = load_chat_runtime()
        schema = getattr(connection, 'schema_name', '') or ''
        result = ChatTurnUseCase(
            _repo(),
            registry,
            policy=policy,
            run_repository=DjangoAssistantAgentRunRepository(),
            credential_repository=DjangoAssistantCredentialRepository(),
            tenant_schema=schema,
            actor_user_id=request.user.id,
        ).execute(
            user_id=request.user.id,
            message=body['message'],
            conversation_id=body.get('conversation_id'),
            ui_context=body.get('ui_context'),
        )
        return wrap_response(result.model_dump(mode='json'))


class AssistantConversationListView(APIView):
    permission_classes = _ASSISTANT_PERMISSIONS
    subscription_functionality = ASSISTANT_CHAT_FEATURE
    subscription_check_quota = False

    @validated_query(AssistantConversationListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        filters = query.filters
        items = ListConversationsUseCase(_repo()).execute(
            user_id=request.user.id,
            limit=filters.get('limit', 20),
            q=filters.get('q'),
        )
        return wrap_response([i.model_dump(mode='json') for i in items])


class AssistantConversationDetailView(APIView):
    permission_classes = _ASSISTANT_PERMISSIONS
    subscription_functionality = ASSISTANT_CHAT_FEATURE
    subscription_check_quota = False

    def get(self, request, conversation_id: uuid.UUID, *args, **kwargs):
        messages = GetConversationMessagesUseCase(_repo()).execute(
            user_id=request.user.id,
            conversation_id=conversation_id,
        )
        return wrap_response({
            'conversation_id': str(conversation_id),
            'messages': [m.model_dump(mode='json') for m in messages],
        })

    @validated_body(RenameConversationBody)
    def patch(self, request, conversation_id: uuid.UUID, *args, body: dict, **kwargs):
        summary = RenameConversationUseCase(_repo()).execute(
            user_id=request.user.id,
            conversation_id=conversation_id,
            title=body['title'],
        )
        return wrap_response(summary.model_dump(mode='json'))
