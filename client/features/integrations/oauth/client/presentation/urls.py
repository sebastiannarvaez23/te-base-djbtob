from django.urls import path

from client.features.integrations.oauth.client.presentation.api import (
    IntegrationApplicationDetailView,
    IntegrationApplicationDisableView,
    IntegrationApplicationEnableView,
    IntegrationApplicationListCreateView,
    IntegrationApplicationRevokeView,
    IntegrationApplicationRotateSecretView,
    IntegrationScopeListView,
    OAuthTokenAPIView,
)

urlpatterns = [
    path('token/', OAuthTokenAPIView.as_view(), name='integration-oauth-token'),
    path('scopes/', IntegrationScopeListView.as_view(), name='integration-oauth-scopes'),
    path('apps/', IntegrationApplicationListCreateView.as_view(), name='integration-oauth-apps'),
    path(
        'apps/<uuid:pk>/',
        IntegrationApplicationDetailView.as_view(),
        name='integration-oauth-app-detail',
    ),
    path(
        'apps/<uuid:pk>/enable/',
        IntegrationApplicationEnableView.as_view(),
        name='integration-oauth-app-enable',
    ),
    path(
        'apps/<uuid:pk>/disable/',
        IntegrationApplicationDisableView.as_view(),
        name='integration-oauth-app-disable',
    ),
    path(
        'apps/<uuid:pk>/revoke/',
        IntegrationApplicationRevokeView.as_view(),
        name='integration-oauth-app-revoke',
    ),
    path(
        'apps/<uuid:pk>/rotate-secret/',
        IntegrationApplicationRotateSecretView.as_view(),
        name='integration-oauth-app-rotate-secret',
    ),
]
