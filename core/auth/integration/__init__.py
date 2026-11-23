"""Authentication plane for external Integration Applications.

Isolated from admin/client cookie JWT:
  - Bearer access tokens (no HttpOnly cookies)
  - ``user_type=integration`` / ``aud=base.integration``
  - Dedicated signing secret (``INTEGRATION_JWT_SECRET``)
"""

from core.auth.integration.authentication import IntegrationBearerAuthentication
from core.auth.integration.permissions import HasIntegrationScope, IntegrationPlanAccess
from core.auth.integration.principal import IntegrationPrincipal

__all__ = [
    'IntegrationBearerAuthentication',
    'HasIntegrationScope',
    'IntegrationPlanAccess',
    'IntegrationPrincipal',
]
