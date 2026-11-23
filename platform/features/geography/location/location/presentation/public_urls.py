from django.urls import path

from platform.features.geography.location.location.presentation.public_api import (
    PublicCityCatalogView,
    PublicCountryCatalogView,
    PublicDepartmentCatalogView,
)

urlpatterns = [
    path('countries/', PublicCountryCatalogView.as_view(), name='public-geo-countries'),
    path('departments/', PublicDepartmentCatalogView.as_view(), name='public-geo-departments'),
    path('cities/', PublicCityCatalogView.as_view(), name='public-geo-cities'),
]
