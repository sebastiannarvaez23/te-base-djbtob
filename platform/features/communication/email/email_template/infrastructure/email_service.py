"""Compat: el transporte vive en ``core.email``."""

from core.email.infrastructure.smtp import DjangoEmailService, SmtpEmailService

__all__ = ['DjangoEmailService', 'SmtpEmailService']
