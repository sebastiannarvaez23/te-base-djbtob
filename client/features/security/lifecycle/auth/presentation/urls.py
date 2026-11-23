from django.urls import path

from client.features.security.lifecycle.auth.presentation.api import (
    ChangePasswordAPIView,
    ConfirmEmailAPIView,
    PasswordResetConfirmAPIView,
    PasswordResetRequestAPIView,
    PasswordResetValidateAPIView,
    ResendConfirmationAPIView,
    ResendTwoFactorAPIView,
    UserLoginAPIView,
    UserActivityAPIView,
    UserLogoutAPIView,
    UserMeAPIView,
    UserRefreshAPIView,
    VerifyTwoFactorAPIView,
    TrustedDeviceListAPIView,
    TrustedDeviceRevokeAPIView,
)

urlpatterns = [
    path('login/', UserLoginAPIView.as_view(), name='login'),
    path('login/verify-2fa/', VerifyTwoFactorAPIView.as_view(), name='login-verify-2fa'),
    path('login/resend-2fa/', ResendTwoFactorAPIView.as_view(), name='login-resend-2fa'),
    path('trusted-devices/', TrustedDeviceListAPIView.as_view(), name='trusted-devices'),
    path(
        'trusted-devices/<uuid:device_id>/',
        TrustedDeviceRevokeAPIView.as_view(),
        name='trusted-device-revoke',
    ),
    path('logout/', UserLogoutAPIView.as_view(), name='logout'),
    path('activity/', UserActivityAPIView.as_view(), name='activity'),
    path('me/', UserMeAPIView.as_view(), name='me'),
    path('refresh/', UserRefreshAPIView.as_view(), name='refresh'),
    path('confirm-email/', ConfirmEmailAPIView.as_view(), name='confirm-email'),
    path('resend-confirmation/', ResendConfirmationAPIView.as_view(), name='resend-confirmation'),
    path('password-reset/request/', PasswordResetRequestAPIView.as_view(), name='password-reset-request'),
    path('password-reset/validate/', PasswordResetValidateAPIView.as_view(), name='password-reset-validate'),
    path('password-reset/confirm/', PasswordResetConfirmAPIView.as_view(), name='password-reset-confirm'),
    path('password/change/', ChangePasswordAPIView.as_view(), name='password-change'),
]
