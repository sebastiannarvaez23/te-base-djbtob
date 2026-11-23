from django.urls import path

from .api import (
    FieldMappingDetailView,
    FieldMappingListCreateView,
    IntegrationConnectionDetailView,
    IntegrationConnectionListCreateView,
    IntegrationConnectionTestView,
    SyncRunListView,
)

urlpatterns = [
    path('connections/', IntegrationConnectionListCreateView.as_view(), name='integration-connections'),
    path('connections/<uuid:pk>/', IntegrationConnectionDetailView.as_view(), name='integration-connection-detail'),
    path('connections/<uuid:pk>/test/', IntegrationConnectionTestView.as_view(), name='integration-connection-test'),
    path('mappings/', FieldMappingListCreateView.as_view(), name='integration-mappings'),
    path('mappings/<uuid:pk>/', FieldMappingDetailView.as_view(), name='integration-mapping-detail'),
    path('sync-runs/', SyncRunListView.as_view(), name='integration-sync-runs'),
]
