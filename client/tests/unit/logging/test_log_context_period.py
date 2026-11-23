"""LogContext carries the active subscription period id from the request."""
import uuid
from types import SimpleNamespace
from unittest import TestCase

from client.features.logging.facade.context import LogContextBuilder


class TestLogContextPeriod(TestCase):

    def _request(self, **extra):
        data = dict(
            user=SimpleNamespace(is_authenticated=False, pk=None),
            tenant=SimpleNamespace(id=7),
            request_id='req-1',
            META={'REMOTE_ADDR': '127.0.0.1', 'HTTP_USER_AGENT': 'test'},
        )
        data.update(extra)
        return SimpleNamespace(**data)

    def test_from_request_stamps_company_subscription_id(self):
        period_id = '11111111-1111-1111-1111-111111111111'
        ctx = LogContextBuilder.from_request(
            self._request(company_subscription_id=period_id),
        )
        self.assertIsInstance(ctx.company_subscription_id, uuid.UUID)
        self.assertEqual(ctx.company_subscription_id, uuid.UUID(period_id))

    def test_from_request_keeps_uuid_instance(self):
        period_id = uuid.UUID('11111111-1111-1111-1111-111111111111')
        ctx = LogContextBuilder.from_request(
            self._request(company_subscription_id=period_id),
        )
        self.assertEqual(ctx.company_subscription_id, period_id)

    def test_from_request_invalid_period_is_none(self):
        ctx = LogContextBuilder.from_request(
            self._request(company_subscription_id='not-a-uuid'),
        )
        self.assertIsNone(ctx.company_subscription_id)

    def test_from_request_without_period_is_none(self):
        ctx = LogContextBuilder.from_request(self._request())
        self.assertIsNone(ctx.company_subscription_id)

    def test_from_request_blank_period_is_none(self):
        ctx = LogContextBuilder.from_request(
            self._request(company_subscription_id=''),
        )
        self.assertIsNone(ctx.company_subscription_id)
