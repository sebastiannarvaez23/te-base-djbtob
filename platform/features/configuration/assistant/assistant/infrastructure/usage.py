"""Uso 24 h del assistant (best-effort, recorre schemas tenant)."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone
from django_tenants.utils import get_tenant_model, schema_context

from platform.features.configuration.assistant.assistant.domain.schemas import AssistantUsageSchema

logger = logging.getLogger('app.ai')


def collect_usage_24h() -> AssistantUsageSchema:
    since = timezone.now() - timedelta(hours=24)
    messages = 0
    conversations = 0
    errors = 0
    try:
        Tenant = get_tenant_model()
        tenants = Tenant.objects.exclude(schema_name='public')
    except Exception as exc:
        logger.info('assistant usage: cannot list tenants (%s)', exc)
        return AssistantUsageSchema()

    for tenant in tenants:
        try:
            with schema_context(tenant.schema_name):
                from client.features.communication.assistant.chat.models import (
                    AssistantConversation,
                    AssistantMessage,
                    AssistantToolCall,
                )
                messages += AssistantMessage.objects.filter(
                    role='user', created_at__gte=since,
                ).count()
                conversations += AssistantConversation.objects.filter(
                    updated_at__gte=since,
                ).count()
                errors += AssistantToolCall.objects.filter(
                    success=False, created_at__gte=since,
                ).count()
        except Exception as exc:
            logger.info(
                'assistant usage skipped schema=%s (%s)',
                getattr(tenant, 'schema_name', '?'), exc,
            )
    return AssistantUsageSchema(
        messages_24h=messages,
        conversations_24h=conversations,
        quota_hits_24h=0,
        errors_24h=errors,
    )
