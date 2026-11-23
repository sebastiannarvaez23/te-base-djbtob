from django.urls import path
from client.features.security.identity.identity.presentation.api import (
    UserPreferencesAPIView,
    UserProfileAPIView,
    UserProfilePictureAPIView,
)

urlpatterns = [
    path('preferences/', UserPreferencesAPIView.as_view(), name='user-preferences'),
    path('profile/', UserProfileAPIView.as_view(), name='user-profile'),
    path('profile/picture/', UserProfilePictureAPIView.as_view(), name='user-profile-picture'),
]
