from django.urls import path

from platform.features.security.auth.auth.presentation.api import (
    AdminActivityAPIView,
    AdminChangePasswordAPIView,
    AdminLoginAPIView,
    AdminLogoutAPIView,
    AdminMeAPIView,
    AdminRefreshAPIView,
    AdminResendTwoFactorAPIView,
    AdminVerifyTwoFactorAPIView,
)

urlpatterns = [
    path('login/', AdminLoginAPIView.as_view(), name='platform-admin-login'),
    path(
        'login/verify-2fa/',
        AdminVerifyTwoFactorAPIView.as_view(),
        name='platform-admin-verify-2fa',
    ),
    path(
        'login/resend-2fa/',
        AdminResendTwoFactorAPIView.as_view(),
        name='platform-admin-resend-2fa',
    ),
    path(
        'password/change/',
        AdminChangePasswordAPIView.as_view(),
        name='platform-admin-password-change',
    ),
    path('logout/', AdminLogoutAPIView.as_view(), name='platform-admin-logout'),
    path('me/', AdminMeAPIView.as_view(), name='platform-admin-me'),
    path('activity/', AdminActivityAPIView.as_view(), name='platform-admin-activity'),
    path('refresh/', AdminRefreshAPIView.as_view(), name='platform-admin-refresh'),
]
