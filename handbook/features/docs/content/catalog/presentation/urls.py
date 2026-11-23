from django.urls import path

from handbook.features.docs.content.catalog.presentation.api import (
    HandbookHelpView,
    HandbookPageView,
    HandbookSearchView,
    HandbookTreeView,
    ManageChangeApproveView,
    ManageChangeRejectView,
    ManageChangeRequestListView,
    ManageFeatureListView,
    ManagePageDetailView,
    ManagePageListView,
)

urlpatterns = [
    path('tree/', HandbookTreeView.as_view()),
    path('help/', HandbookHelpView.as_view()),
    path('pages/<slug:slug>/', HandbookPageView.as_view()),
    path('search/', HandbookSearchView.as_view()),
    path('manage/pages/', ManagePageListView.as_view()),
    path('manage/pages/<uuid:page_id>/', ManagePageDetailView.as_view()),
    path('manage/features/', ManageFeatureListView.as_view()),
    path('manage/change-requests/', ManageChangeRequestListView.as_view()),
    path('manage/change-requests/<uuid:request_id>/approve/', ManageChangeApproveView.as_view()),
    path('manage/change-requests/<uuid:request_id>/reject/', ManageChangeRejectView.as_view()),
]
