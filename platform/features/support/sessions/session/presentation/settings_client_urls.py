"""Client URL wiring for support settings singleton."""

from django.urls import path

from platform.features.support.sessions.session.presentation.api import (
    ClientSupportSettingsView,
)

urlpatterns = [
    path('', ClientSupportSettingsView.as_view()),
]
