from django.urls import path

from platform.features.security.access.roles.presentation.api import (
    AdminFeaturesCatalogAPIView,
    AdminModulesCatalogAPIView,
    AdminRoleDetailAPIView,
    AdminRoleFeaturesAPIView,
    AdminRoleListCreateAPIView,
)

urlpatterns = [
    path('', AdminRoleListCreateAPIView.as_view(), name='platform-role-list'),
    path('modules/', AdminModulesCatalogAPIView.as_view(), name='platform-role-modules-catalog'),
    path('features/', AdminFeaturesCatalogAPIView.as_view(), name='platform-role-features-catalog'),
    path('<uuid:role_id>/', AdminRoleDetailAPIView.as_view(), name='platform-role-detail'),
    path('<uuid:role_id>/features/', AdminRoleFeaturesAPIView.as_view(), name='platform-role-features'),
]
