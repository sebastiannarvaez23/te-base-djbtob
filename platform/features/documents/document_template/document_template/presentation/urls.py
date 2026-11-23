from django.urls import path

from platform.features.documents.document_template.document_template.presentation.api import (
    DocumentTemplateDetailView,
    DocumentTemplateGeneratedDownloadView,
    DocumentTemplateGeneratedListView,
    DocumentTemplateListCreateView,
    DocumentTemplatePreviewPathView,
    DocumentTemplatePreviewView,
)

urlpatterns = [
    path('', DocumentTemplateListCreateView.as_view()),
    path('<uuid:pk>/', DocumentTemplateDetailView.as_view()),
    path('<str:code>/preview/', DocumentTemplatePreviewView.as_view()),
    path('<str:code>/preview-path/', DocumentTemplatePreviewPathView.as_view()),
    path('<str:code>/generated/', DocumentTemplateGeneratedListView.as_view()),
    path('<str:code>/generated/download/', DocumentTemplateGeneratedDownloadView.as_view()),
]
