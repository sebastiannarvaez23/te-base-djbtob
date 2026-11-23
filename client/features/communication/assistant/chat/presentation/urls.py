from django.urls import path

from client.features.communication.assistant.chat.presentation.api import (
    AssistantChatView,
    AssistantConversationDetailView,
    AssistantConversationListView,
    AssistantStatusView,
)

urlpatterns = [
    path('status/', AssistantStatusView.as_view(), name='assistant-status'),
    path('chat/', AssistantChatView.as_view(), name='assistant-chat'),
    path('conversations/', AssistantConversationListView.as_view(), name='assistant-conversations'),
    path(
        'conversations/<uuid:conversation_id>/',
        AssistantConversationDetailView.as_view(),
        name='assistant-conversation-detail',
    ),
]
