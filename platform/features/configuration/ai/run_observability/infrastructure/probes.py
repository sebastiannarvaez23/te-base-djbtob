"""Barrido acotado de AgentRun en schemas tenant (evita impacto PG desmedido)."""

from __future__ import annotations

import logging
from typing import Optional

from django_tenants.utils import get_tenant_model, schema_context

from platform.features.configuration.ai.run_observability.domain.interfaces import IAgentRunProbe
from platform.features.configuration.ai.run_observability.domain.schemas import (
    AgentRunListItemSchema,
)

logger = logging.getLogger('app.ai')

# Caps: no escanear infinitos tenants ni filas por schema.
DEFAULT_PER_TENANT = 20
DEFAULT_MAX_TENANTS = 50


class TenantAgentRunProbe(IAgentRunProbe):

    def collect_recent(
        self,
        *,
        status: Optional[str] = None,
        per_tenant_limit: int = DEFAULT_PER_TENANT,
        max_tenants: int = DEFAULT_MAX_TENANTS,
    ) -> list[AgentRunListItemSchema]:
        out: list[AgentRunListItemSchema] = []
        try:
            Tenant = get_tenant_model()
            tenants = list(
                Tenant.objects.exclude(schema_name='public').order_by('-id')[:max_tenants],
            )
        except Exception as exc:
            logger.info('agent run probe: cannot list tenants (%s)', exc)
            return out

        for tenant in tenants:
            schema = getattr(tenant, 'schema_name', None)
            if not schema:
                continue
            try:
                with schema_context(schema):
                    from client.features.communication.assistant.chat.models import (
                        AssistantAgentRun,
                    )
                    qs = AssistantAgentRun.objects.all().order_by('-created_at')
                    if status:
                        qs = qs.filter(status=status)
                    for row in qs[:per_tenant_limit]:
                        out.append(AgentRunListItemSchema(
                            id=row.id,
                            tenant_schema=schema,
                            user_id=row.user_id,
                            conversation_id=row.conversation_id,
                            status=row.status,
                            provider=row.provider or '',
                            model_id=row.model_id or '',
                            degraded=bool(row.degraded),
                            cancel_requested=bool(row.cancel_requested),
                            step_count=int(row.step_count or 0),
                            error_code=row.error_code or '',
                            started_at=row.started_at,
                            finished_at=row.finished_at,
                            created_at=row.created_at,
                        ))
            except Exception as exc:
                logger.info('agent run probe skipped schema=%s (%s)', schema, exc)
        return out
