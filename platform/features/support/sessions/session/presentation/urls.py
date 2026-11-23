from django.urls import path

from platform.features.support.sessions.session.presentation.api import (
    ClientActiveSupportSessionView,
    ClientCreateSupportSessionView,
    ClientSupportSessionCancelView,
    ClientSupportSessionMessagesView,
    ClientSupportSessionRatingView,
    ClientSupportSessionReadView,
)

urlpatterns = [
    path('me/active/', ClientActiveSupportSessionView.as_view()),
    path('', ClientCreateSupportSessionView.as_view()),
    path('<uuid:session_id>/messages/', ClientSupportSessionMessagesView.as_view()),
    path('<uuid:session_id>/read/', ClientSupportSessionReadView.as_view()),
    path('<uuid:session_id>/cancel/', ClientSupportSessionCancelView.as_view()),
    path('<uuid:session_id>/rating/', ClientSupportSessionRatingView.as_view()),
]
