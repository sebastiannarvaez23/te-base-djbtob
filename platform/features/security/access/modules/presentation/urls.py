from django.urls import path

from platform.features.security.access.modules.presentation.api import (
    ModuleAdminListAPIView,
    ModuleCreateAPIView,
    ModuleDetailAPIView,
    ModuleListAPIView,
    ModuleReorderAPIView,
    ModuleToggleAPIView,
)

urlpatterns = [
    path('', ModuleListAPIView.as_view(), name='module-list'),
    path('admin/', ModuleAdminListAPIView.as_view(), name='module-admin-list'),
    path('create/', ModuleCreateAPIView.as_view(), name='module-create'),
    path('reorder/', ModuleReorderAPIView.as_view(), name='module-reorder'),
    path('<uuid:module_id>/', ModuleDetailAPIView.as_view(), name='module-detail'),
    path('<uuid:module_id>/toggle/', ModuleToggleAPIView.as_view(), name='module-toggle'),
]
