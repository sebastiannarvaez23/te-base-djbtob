"""Helpers compartidos para tests de core.email."""

from core.email.domain.schemas import SendEmailMessage


def email_message(**overrides) -> SendEmailMessage:
    payload: dict = {
        'to': ['a@base.local'],
        'subject': 'Hi',
        'html_body': '<p>Hi</p>',
    }
    payload.update(overrides)
    return SendEmailMessage(**payload)
