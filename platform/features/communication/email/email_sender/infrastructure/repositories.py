from typing import Optional
from platform.features.communication.email.email_sender.models import EmailSender
from platform.features.communication.email.email_sender.domain.interfaces import IEmailSenderRepository


class DjangoEmailSenderRepository(IEmailSenderRepository):
    def get_all(self, filters: dict | None = None) -> list[EmailSender]:
        qs = EmailSender.objects.all()
        f = filters or {}
        if 'code' in f:
            qs = qs.filter(code__icontains=f['code'])
        if 'name' in f:
            qs = qs.filter(name__icontains=f['name'])
        if 'email' in f:
            qs = qs.filter(email__icontains=f['email'])
        if 'is_active' in f:
            qs = qs.filter(is_active=f['is_active'])
        if 'is_default' in f:
            qs = qs.filter(is_default=f['is_default'])
        return list(qs)

    def get_by_id(self, sender_id) -> Optional[EmailSender]:
        try:
            return EmailSender.objects.get(id=sender_id)
        except EmailSender.DoesNotExist:
            return None

    def get_by_code(self, code: str) -> Optional[EmailSender]:
        try:
            return EmailSender.objects.get(code=code)
        except EmailSender.DoesNotExist:
            return None

    def get_default(self) -> Optional[EmailSender]:
        return EmailSender.objects.filter(is_default=True).first()

    def create(self, data: dict) -> EmailSender:
        return EmailSender.objects.create(**data)

    def update(self, sender: EmailSender, data: dict) -> EmailSender:
        for key, val in data.items():
            setattr(sender, key, val)
        sender.save()
        return sender

    def delete(self, sender: EmailSender) -> None:
        sender.delete()
