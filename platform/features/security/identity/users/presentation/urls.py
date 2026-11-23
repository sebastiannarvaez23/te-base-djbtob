from django.urls import path

from platform.features.security.identity.users.presentation.api import (
    AdminUserDetailAPIView,
    AdminUserListCreateAPIView,
    AdminUserToggleActiveAPIView,
)

urlpatterns = [
    path('', AdminUserListCreateAPIView.as_view(), name='platform-user-list'),
    path('<uuid:user_id>/', AdminUserDetailAPIView.as_view(), name='platform-user-detail'),
    path('<uuid:user_id>/toggle-active/', AdminUserToggleActiveAPIView.as_view(), name='platform-user-toggle-active'),
    # Backward-compatible alias used by older clients.
    path('<uuid:user_id>/deactivate/', AdminUserToggleActiveAPIView.as_view(), name='platform-user-deactivate'),
]
