from django.urls import path

from client.features.communication.assistant.credentials.presentation.api import (
    AssistantCredentialDetailView,
    AssistantCredentialListCreateView,
)

urlpatterns = [
    path('', AssistantCredentialListCreateView.as_view(), name='assistant-credentials'),
    path(
        '<uuid:credential_id>/',
        AssistantCredentialDetailView.as_view(),
        name='assistant-credential-detail',
    ),
]
