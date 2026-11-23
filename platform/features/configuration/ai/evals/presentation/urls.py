from django.urls import path

from .api import EvalSuiteListView, EvalSuiteRunView

urlpatterns = [
    path('', EvalSuiteListView.as_view(), name='platform-ai-evals'),
    path('run/', EvalSuiteRunView.as_view(), name='platform-ai-evals-run'),
]
