"""Unit tests of SendEmailBody input validation."""

import pytest

from core.validators import ValidationCode
from platform.features.communication.email.email_template.presentation.bodies import SendEmailBody

pytestmark = pytest.mark.unit


class TestSendEmailBody:

    def test_valid_payload(self):
        body = SendEmailBody({
            'template_code': 'WELCOME',
            'to': ['ops@base.local'],
        })
        ok, errors = body.validate()
        assert ok, errors
        assert body.validated_data['to'] == ['ops@base.local']
        assert body.validated_data['cc'] == []
        assert body.validated_data['attachments'] == []

    def test_rejects_invalid_recipient_email(self):
        body = SendEmailBody({
            'template_code': 'WELCOME',
            'to': ['not-an-email'],
        })
        ok, errors = body.validate()
        assert ok is False
        assert errors[0].field == 'to[0]'
        assert errors[0].code == ValidationCode.INVALID_EMAIL

    def test_rejects_empty_to(self):
        body = SendEmailBody({
            'template_code': 'WELCOME',
            'to': [],
        })
        ok, errors = body.validate()
        assert ok is False
        assert errors[0].code == ValidationCode.MIN_ITEMS

    def test_validates_attachment_shape(self):
        body = SendEmailBody({
            'template_code': 'WELCOME',
            'to': ['ops@base.local'],
            'attachments': [{'filename': 'a.pdf', 'content': 'Zm9v'}],
        })
        ok, errors = body.validate()
        assert ok, errors
        att = body.validated_data['attachments'][0]
        assert att['filename'] == 'a.pdf'
        assert att['mimetype'] == 'application/octet-stream'

    def test_rejects_attachment_without_filename(self):
        body = SendEmailBody({
            'template_code': 'WELCOME',
            'to': ['ops@base.local'],
            'attachments': [{'filename': '', 'content': 'Zm9v'}],
        })
        ok, errors = body.validate()
        assert ok is False
        assert errors[0].code == ValidationCode.MIN_LENGTH
