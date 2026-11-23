from django.urls import path

from platform.features.communication.messaging.inbox.presentation.api import (
    AdminInboxArchiveView,
    AdminInboxListView,
    AdminInboxMarkAllReadView,
    AdminInboxMarkReadView,
    AdminInboxUnreadCountView,
    AdminNotificationView,
    ResourceTypeDetailView,
    ResourceTypeView,
)

urlpatterns = [
    path('notify/', AdminNotificationView.as_view()),
    path('sent/', AdminNotificationView.as_view()),
    path('', AdminInboxListView.as_view()),
    path('unread-count/', AdminInboxUnreadCountView.as_view()),
    path('read-all/', AdminInboxMarkAllReadView.as_view()),
    path('resource-types/', ResourceTypeView.as_view()),
    path('resource-types/<str:code>/', ResourceTypeDetailView.as_view()),
    path('<uuid:pk>/read/', AdminInboxMarkReadView.as_view()),
    path('<uuid:pk>/archive/', AdminInboxArchiveView.as_view()),
]
