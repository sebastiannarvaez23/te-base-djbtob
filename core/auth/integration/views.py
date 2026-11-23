"""Base controller for endpoints consumed by Integration Applications."""
from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured
from rest_framework.views import APIView

from core.auth.integration.authentication import IntegrationBearerAuthentication
from core.auth.integration.permissions import HasIntegrationScope, IntegrationPlanAccess


class IntegrationAPIView(APIView):
    """Independent from the frontend controllers.

    Only integration Bearer tokens authenticate (session cookies are ignored),
    and every ``required_scopes`` entry must be in the token and still enabled
    for the tenant. Cookie-based gates (``CatalogAccessMiddleware``) do not run
    for these requests, so the plan / catalog check lives here.
    """

    authentication_classes = [IntegrationBearerAuthentication]
    permission_classes = [HasIntegrationScope, IntegrationPlanAccess]
    required_scopes: tuple[str, ...] = ()

    @classmethod
    def as_view(cls, **initkwargs):
        if not cls.required_scopes:
            raise ImproperlyConfigured(f'{cls.__name__} must declare required_scopes.')
        return super().as_view(**initkwargs)
