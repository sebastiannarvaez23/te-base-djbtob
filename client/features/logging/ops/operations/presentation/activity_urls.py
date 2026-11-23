from django.urls import path

from client.features.logging.ops.operations.presentation.api import RecentActivityView

urlpatterns = [
    path('', RecentActivityView.as_view(), name='recent-activity'),
]
