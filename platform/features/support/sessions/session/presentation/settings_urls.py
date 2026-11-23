"""Admin URL wiring for support settings singleton."""

from django.urls import path

from platform.features.support.sessions.session.presentation.admin_api import (
    AdminSupportSettingsView,
)

urlpatterns = [
    path('', AdminSupportSettingsView.as_view()),
]
