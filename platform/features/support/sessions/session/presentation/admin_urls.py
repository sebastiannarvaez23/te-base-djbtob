from django.urls import path

from platform.features.support.sessions.session.presentation.admin_api import (
    AdminActiveSupportSessionView,
    AdminSupportSessionAcceptView,
    AdminSupportSessionCloseView,
    AdminSupportSessionDetailView,
    AdminSupportSessionEventsView,
    AdminSupportSessionListView,
    AdminSupportSessionMessagesView,
    AdminSupportSessionReadView,
)

urlpatterns = [
    path('me/active/', AdminActiveSupportSessionView.as_view()),
    path('', AdminSupportSessionListView.as_view()),
    path('<uuid:session_id>/', AdminSupportSessionDetailView.as_view()),
    path('<uuid:session_id>/accept/', AdminSupportSessionAcceptView.as_view()),
    path('<uuid:session_id>/messages/', AdminSupportSessionMessagesView.as_view()),
    path('<uuid:session_id>/events/', AdminSupportSessionEventsView.as_view()),
    path('<uuid:session_id>/read/', AdminSupportSessionReadView.as_view()),
    path('<uuid:session_id>/close/', AdminSupportSessionCloseView.as_view()),
]
