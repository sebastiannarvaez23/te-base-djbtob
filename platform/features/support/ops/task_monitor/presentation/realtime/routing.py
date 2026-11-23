from django.urls import path

from platform.features.support.ops.task_monitor.presentation.realtime.consumer import (
    TaskMonitorConsumer,
)

websocket_urlpatterns = [
    path('ws/platform/task-monitor/', TaskMonitorConsumer.as_asgi()),
]
