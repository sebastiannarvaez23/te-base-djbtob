from django.urls import path

from platform.features.support.incidents.incident.presentation.admin_api import (
    IncidentDetailView,
    IncidentListView,
    IncidentStatusView,
)

urlpatterns = [
    path('', IncidentListView.as_view(), name='incident-list'),
    path('<uuid:incident_id>/', IncidentDetailView.as_view(), name='incident-detail'),
    path('<uuid:incident_id>/status/', IncidentStatusView.as_view(), name='incident-status'),
]
