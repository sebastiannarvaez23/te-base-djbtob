from django.urls import path

from platform.features.geography.location.location.presentation.api import (
    CityDetailView,
    CityListCreateView,
    CountryDetailView,
    CountryListCreateView,
    DepartmentDetailView,
    DepartmentListCreateView,
    LocationImportTemplateView,
    LocationImportView,
)

urlpatterns = [
    path('countries/', CountryListCreateView.as_view(), name='geo-countries'),
    path('countries/<uuid:pk>/', CountryDetailView.as_view(), name='geo-country-detail'),
    path('departments/', DepartmentListCreateView.as_view(), name='geo-departments'),
    path('departments/<uuid:pk>/', DepartmentDetailView.as_view(), name='geo-department-detail'),
    path('cities/', CityListCreateView.as_view(), name='geo-cities'),
    path('cities/<uuid:pk>/', CityDetailView.as_view(), name='geo-city-detail'),
    path('import/template/', LocationImportTemplateView.as_view(), name='geo-import-template'),
    path('import/', LocationImportView.as_view(), name='geo-import'),
]
