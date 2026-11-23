from django.urls import path

from .api import (
    ConnectorCatalogDetailView,
    ConnectorCatalogListCreateView,
    IntegrationHealthView,
)

urlpatterns = [
    path('', ConnectorCatalogListCreateView.as_view(), name='connector-catalog-list'),
    path('<uuid:pk>/', ConnectorCatalogDetailView.as_view(), name='connector-catalog-detail'),
]
