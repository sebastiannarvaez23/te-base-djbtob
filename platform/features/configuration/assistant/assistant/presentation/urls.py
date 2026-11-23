from django.urls import path

from platform.features.configuration.assistant.assistant.presentation.api import AssistantSettingsView

urlpatterns = [
    path('', AssistantSettingsView.as_view(), name='platform-assistant-settings'),
]
