"""Tests del registro de hooks de core/access (inversión de dependencia que
permite que el middleware reaccione a la expiración sin importar las tareas de
billing)."""
from unittest import TestCase

from core.access import hooks


class TestSubscriptionExpiryHooks(TestCase):

    def setUp(self):
        self._saved = hooks._subscription_expiry_handlers[:]
        hooks._subscription_expiry_handlers.clear()

    def tearDown(self):
        hooks._subscription_expiry_handlers[:] = self._saved

    def test_register_is_idempotent(self):
        def handler(company_id, cs):
            pass
        hooks.register_subscription_expiry_handler(handler)
        hooks.register_subscription_expiry_handler(handler)
        self.assertEqual(hooks._subscription_expiry_handlers.count(handler), 1)

    def test_notify_dispatches_to_every_handler(self):
        calls = []
        hooks.register_subscription_expiry_handler(lambda cid, cs: calls.append((cid, cs)))
        hooks.register_subscription_expiry_handler(lambda cid, cs: calls.append(('b', cid)))
        hooks.notify_subscription_expiry('c1', 'cs-obj')
        self.assertEqual(calls, [('c1', 'cs-obj'), ('b', 'c1')])

    def test_notify_is_best_effort(self):
        """A failing handler never breaks the request path nor blocks others."""
        survived = []

        def boom(cid, cs):
            raise RuntimeError('handler down')

        hooks.register_subscription_expiry_handler(boom)
        hooks.register_subscription_expiry_handler(lambda cid, cs: survived.append(1))
        hooks.notify_subscription_expiry('c1', None)  # must not raise
        self.assertEqual(survived, [1])
