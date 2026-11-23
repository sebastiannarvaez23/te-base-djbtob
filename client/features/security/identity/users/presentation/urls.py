from django.urls import path

from client.features.security.identity.users.presentation.api import (
    CheckCompanyEmailAPIView,
    CheckCompanyUsernameAPIView,
    CompanyUserDetailAPIView,
    CompanyUserToggleActiveAPIView,
    CompanyUsersAPIView,
)

urlpatterns = [
    path('check-username/', CheckCompanyUsernameAPIView.as_view(), name='company-users-check-username'),
    path('check-email/', CheckCompanyEmailAPIView.as_view(), name='company-users-check-email'),
    path('users/', CompanyUsersAPIView.as_view(), name='company-users'),
    path('users/<uuid:user_id>/', CompanyUserDetailAPIView.as_view(), name='company-user-detail'),
    path('users/<uuid:user_id>/toggle-active/', CompanyUserToggleActiveAPIView.as_view(), name='company-user-toggle'),
]
