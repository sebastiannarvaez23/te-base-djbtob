"""Rutas del handbook: cada endpoint resuelve a su vista."""

import pytest
from django.urls import resolve

from handbook.features.docs.content.catalog.presentation import api

pytestmark = pytest.mark.unit


@pytest.mark.parametrize('path, view', [
    ('tree/', api.HandbookTreeView),
    ('help/', api.HandbookHelpView),
    ('pages/pedidos/', api.HandbookPageView),
    ('search/', api.HandbookSearchView),
    ('manage/pages/', api.ManagePageListView),
    ('manage/pages/0190c7a0-0000-7000-8000-000000000000/', api.ManagePageDetailView),
    ('manage/features/', api.ManageFeatureListView),
    ('manage/change-requests/', api.ManageChangeRequestListView),
    ('manage/change-requests/0190c7a0-0000-7000-8000-000000000000/approve/', api.ManageChangeApproveView),
    ('manage/change-requests/0190c7a0-0000-7000-8000-000000000000/reject/', api.ManageChangeRejectView),
])
def test_routes_resolve(path, view):
    match = resolve(f'/{path}', urlconf='handbook.features.docs.content.catalog.presentation.urls')
    assert match.func.view_class is view
