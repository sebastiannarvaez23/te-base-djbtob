from django.urls import path

from client.features.security.access.roles.presentation.api import (
    FeaturesListAPIView,
    GenericRoleDetailAPIView,
    GenericRoleFeaturesAPIView,
    GenericRolesListCreateAPIView,
    RoleDetailAPIView,
    RoleFeaturesAPIView,
    RolCompanyAccessAPIView,
    RolesListCreateAPIView,
)

urlpatterns = [
    path('', RolesListCreateAPIView.as_view(), name='company-roles'),
    path('features/', FeaturesListAPIView.as_view(), name='company-features-catalog'),
    path('generic/', GenericRolesListCreateAPIView.as_view(), name='company-generic-roles'),
    path('generic/<uuid:role_id>/', GenericRoleDetailAPIView.as_view(), name='company-generic-role-detail'),
    path('generic/<uuid:role_id>/features/', GenericRoleFeaturesAPIView.as_view(), name='company-generic-role-features'),
    path('<uuid:role_id>/', RoleDetailAPIView.as_view(), name='company-role-detail'),
    path('<uuid:role_id>/features/', RoleFeaturesAPIView.as_view(), name='company-role-features'),
    path('<uuid:role_id>/access/', RolCompanyAccessAPIView.as_view(), name='company-role-access'),
]
