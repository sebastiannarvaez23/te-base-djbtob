from django.urls import path

from platform.features.security.identity.identity.presentation.api import (
    AdminUserPreferencesAPIView,
    AdminUserProfileAPIView,
    AdminUserProfilePictureAPIView,
)

urlpatterns = [
    path('preferences/', AdminUserPreferencesAPIView.as_view(), name='platform-admin-preferences'),
    path('profile/', AdminUserProfileAPIView.as_view(), name='platform-admin-profile'),
    path('profile/picture/', AdminUserProfilePictureAPIView.as_view(), name='platform-admin-profile-picture'),
]
