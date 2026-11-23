import logging

from celery import shared_task
from django.utils import timezone

from core.tasks.base import BaseTask, redis_lock

from platform.features.billing.commerce.promotion import composition
from platform.features.billing.commerce.promotion.application.use_cases import ExpireVouchersUseCase
from platform.features.billing.commerce.promotion.infrastructure.repositories import (
    DjangoPromotionVoucherRepository,
)

logger = logging.getLogger('app.tasks')

_LOCK_TTL = 900


@shared_task(
    base=BaseTask,
    name='promotion.expire_vouchers',
    bind=True,
    soft_time_limit=300,
    time_limit=420,
)
def expire_promotion_vouchers_task(self):
    with redis_lock('promotion:expire_vouchers', ttl_seconds=_LOCK_TTL) as acquired:
        if not acquired:
            return {'skipped': True}
        count = ExpireVouchersUseCase(DjangoPromotionVoucherRepository()).execute(
            now=timezone.now(),
        )
        logger.info('expire_promotion_vouchers: %s vouchers expired', count)
        return {'expired': count}


@shared_task(
    base=BaseTask,
    name='promotion.revert_gift_benefits',
    bind=True,
    soft_time_limit=300,
    time_limit=420,
)
def revert_expired_gift_benefits_task(self):
    with redis_lock('promotion:revert_gift_benefits', ttl_seconds=_LOCK_TTL) as acquired:
        if not acquired:
            return {'skipped': True}
        reverted = composition.revert_expired_gift_benefits(now=timezone.now())
        logger.info('revert_expired_gift_benefits: %s benefits reverted', reverted)
        return {'reverted': reverted}
