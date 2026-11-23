from django.urls import path

from platform.features.security.identity.sessions.presentation.api import (
    SessionKillAllAPIView,
    SessionKillByCompanyAPIView,
    SessionKillByUserAPIView,
    SessionKillAPIView,
    SessionListAPIView,
)

urlpatterns = [
    path('', SessionListAPIView.as_view(), name='platform-session-list'),
    path('all/', SessionKillAllAPIView.as_view(), name='platform-session-kill-all'),
    path('by-user/<uuid:user_id>/', SessionKillByUserAPIView.as_view(), name='platform-session-kill-by-user'),
    path('by-company/<uuid:company_id>/', SessionKillByCompanyAPIView.as_view(), name='platform-session-kill-by-company'),
    path('<str:session_id>/', SessionKillAPIView.as_view(), name='platform-session-kill'),
]
