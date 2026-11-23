"""Unit tests de FakeEmailService."""

import pytest

from core.email import FakeEmailService
from core.tests.unit.email.helpers import email_message

pytestmark = pytest.mark.unit


class TestFakeEmailService:

    def test_records_send_and_returns_true(self):
        svc = FakeEmailService()
        ok = svc.send(email_message(
            to=['a@base.local'],
            subject='Hi',
            html_body='<p>Hi</p>',
            from_email='noreply@base.local',
            from_name='Base',
        ))
        assert ok is True
        assert len(svc.sent) == 1
        assert svc.sent[0].to == ['a@base.local']
        assert svc.sent[0].subject == 'Hi'
        assert svc.sent[0].from_name == 'Base'
