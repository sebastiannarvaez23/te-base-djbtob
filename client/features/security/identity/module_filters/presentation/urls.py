from django.urls import path

from client.features.security.identity.module_filters.presentation.api import (
    ModuleFilterActivateView,
    ModuleFilterDeactivateView,
    ModuleFilterDetailView,
    ModuleFilterListCreateView,
)

urlpatterns = [
    path('', ModuleFilterListCreateView.as_view(), name='module-filters'),
    path('deactivate/', ModuleFilterDeactivateView.as_view(), name='module-filters-deactivate'),
    path('<uuid:filter_id>/', ModuleFilterDetailView.as_view(), name='module-filter-detail'),
    path(
        '<uuid:filter_id>/activate/',
        ModuleFilterActivateView.as_view(),
        name='module-filter-activate',
    ),
]
