from django.urls import path

from platform.features.support.ops.task_monitor.presentation.admin_api import (
    MonitoredTaskListView,
    TaskRunDetailView,
    TaskRunListView,
    TaskRunLogsView,
)

urlpatterns = [
    path('tasks/', MonitoredTaskListView.as_view(), name='task-monitor-tasks'),
    path(
        'tasks/<str:task_key>/runs/',
        TaskRunListView.as_view(),
        name='task-monitor-runs',
    ),
    path('runs/<uuid:run_id>/', TaskRunDetailView.as_view(), name='task-monitor-run'),
    path(
        'runs/<uuid:run_id>/logs/',
        TaskRunLogsView.as_view(),
        name='task-monitor-run-logs',
    ),
]
