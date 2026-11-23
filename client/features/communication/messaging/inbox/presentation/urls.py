from django.urls import path

from client.features.communication.messaging.inbox.presentation.api import (
    ArchiveView,
    InboxListView,
    MarkAllReadView,
    MarkReadView,
    ShareView,
    UnreadCountView,
)

urlpatterns = [
    path('', InboxListView.as_view()),
    path('unread-count/', UnreadCountView.as_view()),
    path('read-all/', MarkAllReadView.as_view()),
    path('share/', ShareView.as_view()),
    path('<uuid:pk>/read/', MarkReadView.as_view()),
    path('<uuid:pk>/archive/', ArchiveView.as_view()),
]
