from django.urls import path

from client.features.security.access.entity_grants.presentation.api import (
    EntityGrantSetView,
    UserGrantSetView,
)

urlpatterns = [
    path('users/<uuid:key_id>/', UserGrantSetView.as_view(), name='entity-grants-user'),
    path('entities/<uuid:key_id>/', EntityGrantSetView.as_view(), name='entity-grants-entity'),
]
