"""Notification adapter — wraps NotificationService behind INotificationPort."""

from platform.features.billing.commerce.promotion.domain.interfaces import INotificationPort
from platform.features.communication.notification.service import NotificationService


class DjangoNotification(INotificationPort):

    def __init__(self, service: NotificationService | None = None):
        self._service = service or NotificationService()

    def send_email(self, *, template_code: str, to: list[str], context: dict) -> bool:
        return bool(self._service.send_email(
            template_code=template_code,
            to=to,
            context=context,
        ))
