"""Celery: send the refund to the payment gateway off the request path."""
import logging

from celery import shared_task

from core.errors import NotFoundException
from core.tasks.base import BaseTask, redis_lock

logger = logging.getLogger('app.tasks')

_LOCK_TTL = 120


@shared_task(
    base=BaseTask,
    name='refund.process_refund_payout',
    bind=True,
    soft_time_limit=90,
    time_limit=120,
    max_retries=5,
    default_retry_delay=60,
)
def process_refund_payout(self, ticket_id: str) -> dict:
    lock_key = f'refund:payout:{ticket_id}'
    with redis_lock(lock_key, ttl_seconds=_LOCK_TTL) as acquired:
        if not acquired:
            return {'skipped': True}
        from ..infrastructure.factory import build_process
        try:
            ticket = build_process().execute(ticket_id)
        except NotFoundException:
            return {'missing': True}
        except Exception as exc:
            logger.exception('process_refund_payout failed for %s', ticket_id)
            raise self.retry(exc=exc)
        return {'ticket': ticket.ticket_number, 'status': ticket.status}
