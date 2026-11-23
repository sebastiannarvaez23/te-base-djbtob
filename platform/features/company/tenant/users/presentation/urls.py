from django.urls import path

from platform.features.company.tenant.users.presentation.api import (
    TenantUserListAPIView,
    TenantUserToggleActiveAPIView,
)

urlpatterns = [
    path('', TenantUserListAPIView.as_view()),
    path('<uuid:user_id>/toggle-active/', TenantUserToggleActiveAPIView.as_view()),
]
