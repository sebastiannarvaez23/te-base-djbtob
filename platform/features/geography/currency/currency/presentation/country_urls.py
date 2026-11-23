from django.urls import path

from platform.features.geography.currency.currency.presentation.api import (
    CountryCurrencyDetailView,
    CountryCurrencyListCreateView,
)

urlpatterns = [
    path(
        '<uuid:country_id>/currencies/',
        CountryCurrencyListCreateView.as_view(),
        name='geo-country-currencies',
    ),
    path(
        '<uuid:country_id>/currencies/<uuid:pk>/',
        CountryCurrencyDetailView.as_view(),
        name='geo-country-currency-detail',
    ),
]
