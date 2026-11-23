"""Vista agregada de salud cross-tenant (soporte)."""

from __future__ import annotations

from django_tenants.utils import get_tenant_model, schema_context

from client.features.integrations.connections.profile.models import IntegrationConnection
from core.trace import trace_layer


class GetIntegrationHealthUseCase:

    @trace_layer('application')
    def execute(self) -> dict:
        Tenant = get_tenant_model()
        degraded = 0
        error = 0
        active = 0
        tenants_with_connections = 0
        details: list[dict] = []

        for tenant in Tenant.objects.exclude(schema_name='public'):
            with schema_context(tenant.schema_name):
                connections = list(
                    IntegrationConnection.objects.values(
                        'id', 'name', 'connector_key', 'environment', 'status', 'last_error',
                    )[:50]
                )
                if not connections:
                    continue
                tenants_with_connections += 1
                for conn in connections:
                    status = conn['status']
                    if status == 'ACTIVE':
                        active += 1
                    elif status == 'DEGRADED':
                        degraded += 1
                    elif status == 'ERROR':
                        error += 1
                    if status in ('DEGRADED', 'ERROR'):
                        details.append({
                            'tenant_schema': tenant.schema_name,
                            'tenant_name': getattr(tenant, 'name', tenant.schema_name),
                            **conn,
                        })

        return {
            'summary': {
                'tenants_with_connections': tenants_with_connections,
                'active_connections': active,
                'degraded_connections': degraded,
                'error_connections': error,
            },
            'issues': details[:100],
        }
