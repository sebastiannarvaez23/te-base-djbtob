"""Domain events for billing-period lifecycle.

Payments and invoice subscribe via their integration adapters. Handlers are
best-effort: a failure never rolls back ``activate_plan``.
"""
from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Callable, Optional

from pydantic import BaseModel, Field

from django.utils import timezone

logger = logging.getLogger('billing.subscription.events')


class PeriodDomainEvent(BaseModel):
    company_id: uuid.UUID
    period_id: uuid.UUID
    occurred_at: datetime = Field(default_factory=lambda: timezone.now())


class PeriodClosed(PeriodDomainEvent):
    """Previous active period replaced by a new license (renew/upgrade)."""


class PeriodIssued(PeriodDomainEvent):
    """New license row is active. ``charge_id`` set when the cobro already exists."""

    subscription_id: uuid.UUID
    charge_id: Optional[uuid.UUID] = None
    closed_period_ids: list[uuid.UUID] = Field(default_factory=list)


class _EventBus:
    def __init__(self) -> None:
        self._handlers: dict[type, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: Callable) -> None:
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)

    def publish(self, event: PeriodDomainEvent) -> None:
        for handler in list(self._handlers.get(type(event), [])):
            try:
                handler(event)
            except Exception:
                logger.exception(
                    'subscription event handler %r failed for %s',
                    handler, type(event).__name__,
                )

    def clear(self) -> None:
        self._handlers.clear()


bus = _EventBus()
subscribe = bus.subscribe
publish = bus.publish
