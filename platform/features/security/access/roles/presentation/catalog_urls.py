from django.urls import path

from platform.features.security.access.roles.presentation.catalog_api import (
    AdminCatalogFeatureDetailAPIView,
    AdminCatalogFeatureListCreateAPIView,
    AdminCatalogModuleDetailAPIView,
    AdminCatalogModuleListCreateAPIView,
    AdminCatalogModuleReorderAPIView,
    AdminCatalogModuleToggleAPIView,
    AdminCatalogSectionDetailAPIView,
    AdminCatalogSectionListCreateAPIView,
    AdminCatalogSectionReorderAPIView,
    AdminCatalogSectionToggleAPIView,
)

urlpatterns = [
    path('sections/', AdminCatalogSectionListCreateAPIView.as_view(), name='admin-catalog-sections'),
    path('sections/reorder/', AdminCatalogSectionReorderAPIView.as_view(), name='admin-catalog-sections-reorder'),
    path('sections/<uuid:section_id>/', AdminCatalogSectionDetailAPIView.as_view(), name='admin-catalog-section-detail'),
    path('sections/<uuid:section_id>/toggle/', AdminCatalogSectionToggleAPIView.as_view(), name='admin-catalog-section-toggle'),
    path('modules/', AdminCatalogModuleListCreateAPIView.as_view(), name='admin-catalog-modules'),
    path('modules/reorder/', AdminCatalogModuleReorderAPIView.as_view(), name='admin-catalog-modules-reorder'),
    path('modules/<uuid:module_id>/', AdminCatalogModuleDetailAPIView.as_view(), name='admin-catalog-module-detail'),
    path('modules/<uuid:module_id>/toggle/', AdminCatalogModuleToggleAPIView.as_view(), name='admin-catalog-module-toggle'),
    path('features/', AdminCatalogFeatureListCreateAPIView.as_view(), name='admin-catalog-features'),
    path('features/<uuid:feature_id>/', AdminCatalogFeatureDetailAPIView.as_view(), name='admin-catalog-feature-detail'),
]
