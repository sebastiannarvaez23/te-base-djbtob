from django.urls import path

from platform.features.support.ops.live_logs.presentation.admin_api import (
    LiveLogChannelsView,
    LiveLogRecentView,
)

urlpatterns = [
    path('channels/', LiveLogChannelsView.as_view(), name='live-logs-channels'),
    path('recent/', LiveLogRecentView.as_view(), name='live-logs-recent'),
]
