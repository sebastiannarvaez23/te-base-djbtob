"""Unit tests del contrato Pydantic SendEmailMessage."""

import pytest
from pydantic import ValidationError

from core.email.domain.schemas import EmailAttachment, SendEmailMessage

pytestmark = pytest.mark.unit


class TestSendEmailMessage:

    def test_requires_recipients(self):
        with pytest.raises(ValidationError):
            SendEmailMessage(to=[], subject='Hi', html_body='<p>Hi</p>')

    def test_requires_subject(self):
        with pytest.raises(ValidationError):
            SendEmailMessage(to=['a@base.local'], html_body='<p>Hi</p>')

    def test_defaults_optional_fields(self):
        msg = SendEmailMessage(to=['a@base.local'], subject='Hi', html_body='<p>Hi</p>')
        assert msg.cc == []
        assert msg.bcc == []
        assert msg.attachments == []
        assert msg.plain_body == ''
        assert msg.from_email == ''

    def test_attachment_requires_filename(self):
        with pytest.raises(ValidationError):
            EmailAttachment(filename='', content='Zm9v')
