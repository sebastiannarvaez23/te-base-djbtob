from django.urls import path

from .api import AgentRunListView

urlpatterns = [
    path('', AgentRunListView.as_view(), name='platform-ai-runs'),
]
