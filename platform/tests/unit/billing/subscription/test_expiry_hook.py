"""Tests del handler ``on_subscription_expiry`` (registrado con el hook de
core/access). Decide entre materializar un relevo pendiente o renovar, y encola
la tarea correspondiente — throttled, y sólo encola (el trabajo pesado va al
worker). Todo mockeado: sin BD, sin caché real, sin Celery."""
import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from django.utils import timezone

from platform.features.billing.subscription.subscription.integration.expiry_hook import (
    on_subscription_expiry,
)

_DOWNGRADE_TASK = (
    'platform.features.billing.subscription.subscription.tasks.downgrades.'
    'apply_pending_downgrade_for_company'
)
_EXPIRE_TASK = (
    'platform.features.billing.subscription.subscription.tasks.expire.'
    'expire_subscription_for_company'
)
_RENEW_TASK = (
    'platform.features.billing.subscription.subscription.tasks.renewals.'
    'renew_subscription_for_company'
)
_CACHES = 'django.core.cache.caches'


def _cs(*, expired=True, pending=None, auto_renew=False):
    delta = timedelta(days=1)
    end = timezone.now() - delta if expired else timezone.now() + delta
    return SimpleNamespace(end_date=end, pending_subscription_id=pending, auto_renew=auto_renew)


def _caches_allowing():
    """Mock de caches donde el guard `add` deja pasar (devuelve True)."""
    caches = MagicMock()
    caches.__getitem__.return_value.add.return_value = True
    return caches


class TestExpiryRouting(TestCase):

    def test_not_expired_is_noop(self):
        with patch(_DOWNGRADE_TASK) as dg, patch(_RENEW_TASK) as rn:
            on_subscription_expiry('c1', _cs(expired=False, auto_renew=True))
        dg.delay.assert_not_called()
        rn.delay.assert_not_called()

    def test_expired_without_pending_or_autorenew_enqueues_expire(self):
        with patch(_CACHES, _caches_allowing()), \
                patch(_EXPIRE_TASK) as ex, patch(_DOWNGRADE_TASK) as dg, patch(_RENEW_TASK) as rn:
            on_subscription_expiry('c1', _cs(pending=None, auto_renew=False))
        ex.delay.assert_called_once_with('c1')
        dg.delay.assert_not_called()
        rn.delay.assert_not_called()

    def test_expired_with_pending_enqueues_downgrade(self):
        with patch(_CACHES, _caches_allowing()), \
                patch(_DOWNGRADE_TASK) as dg, patch(_RENEW_TASK) as rn:
            on_subscription_expiry('c1', _cs(pending=uuid.uuid4(), auto_renew=True))
        dg.delay.assert_called_once_with('c1')
        rn.delay.assert_not_called()   # pending wins over auto_renew

    def test_expired_with_autorenew_enqueues_renewal(self):
        with patch(_CACHES, _caches_allowing()), \
                patch(_DOWNGRADE_TASK) as dg, patch(_RENEW_TASK) as rn:
            on_subscription_expiry('c1', _cs(pending=None, auto_renew=True))
        rn.delay.assert_called_once_with('c1')
        dg.delay.assert_not_called()

    def test_throttle_blocks_second_enqueue_in_window(self):
        caches = MagicMock()
        caches.__getitem__.return_value.add.return_value = False  # window already taken
        with patch(_CACHES, caches), \
                patch(_DOWNGRADE_TASK) as dg, patch(_RENEW_TASK) as rn, patch(_EXPIRE_TASK) as ex:
            on_subscription_expiry('c1', _cs(pending=None, auto_renew=True))
        dg.delay.assert_not_called()
        rn.delay.assert_not_called()
        ex.delay.assert_not_called()

    def test_throttle_blocks_expire_enqueue(self):
        caches = MagicMock()
        caches.__getitem__.return_value.add.return_value = False
        with patch(_CACHES, caches), \
                patch(_EXPIRE_TASK) as ex, patch(_DOWNGRADE_TASK) as dg, patch(_RENEW_TASK) as rn:
            on_subscription_expiry('c1', _cs(pending=None, auto_renew=False))
        ex.delay.assert_not_called()
        dg.delay.assert_not_called()
        rn.delay.assert_not_called()
