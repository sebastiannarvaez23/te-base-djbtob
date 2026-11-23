from django.urls import path

from platform.features.support.incidents.incident.presentation.api import (
    IncidentAttachmentsAPIView,
    ReportIncidentAPIView,
    ReportManualIncidentAPIView,
)

urlpatterns = [
    path('report/', ReportIncidentAPIView.as_view(), name='incident-report'),
    path(
        'report/manual/',
        ReportManualIncidentAPIView.as_view(),
        name='incident-report-manual',
    ),
    path(
        'report/<uuid:incident_id>/attachments/',
        IncidentAttachmentsAPIView.as_view(),
        name='incident-report-attachments',
    ),
]
