"""DRF permissions for Integration Application scopes."""
from __future__ import annotations

from rest_framework.permissions import BasePermission

from core.auth.integration.principal import IntegrationPrincipal
from core.errors import AppErrorCode, AuthException


class HasIntegrationScope(BasePermission):
    """Require an ``IntegrationPrincipal`` holding all declared scopes.

    Views set::

        authentication_classes = [IntegrationBearerAuthentication]
        permission_classes = [HasIntegrationScope]
        required_scopes = ['orders:write']

    No principal → ``False`` (DRF answers 401). Missing scope → ``AUTH_010``.
    """

    def has_permission(self, request, view) -> bool:
        user = getattr(request, 'user', None)
        if not isinstance(user, IntegrationPrincipal):
            return False
        required = getattr(view, 'required_scopes', None) or ()
        missing = sorted(set(required) - user.scopes)
        if missing:
            raise AuthException(
                AppErrorCode.AUTH_SCOPE_DENIED,
                override_detail=(
                    'The access token does not include the scope required by this endpoint: '
                    + ', '.join(missing)
                ),
            )
        return True


class IntegrationPlanAccess(BasePermission):
    """Each required scope must still be enabled for the tenant on every call.

    Tokens live for a while; a plan downgrade or a deactivated module /
    functionality must cut access before the token expires. The request host
    must also resolve the same tenant the token was issued for.
    """

    def has_permission(self, request, view) -> bool:
        user = getattr(request, 'user', None)
        if not isinstance(user, IntegrationPrincipal):
            return False
        tenant = getattr(request, 'tenant', None)
        if tenant is None or getattr(tenant, 'schema_name', None) != user.schema_name:
            raise AuthException(AppErrorCode.AUTH_TOKEN_INVALID)

        from core.access.checker import AccessChecker

        for scope in getattr(view, 'required_scopes', None) or ():
            AccessChecker.ensure_access_or_raise(tenant, scope, check_quota=False)
        return True
