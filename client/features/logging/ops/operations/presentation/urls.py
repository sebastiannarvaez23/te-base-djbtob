from django.urls import path

from client.features.logging.ops.operations.presentation.api import RecordTraceView

urlpatterns = [
    path('', RecordTraceView.as_view(), name='record-trace'),
]
