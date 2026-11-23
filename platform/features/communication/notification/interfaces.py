from abc import ABC, abstractmethod


class INotificationService(ABC):
    """High-level contract for dispatching notifications from any module."""

    @abstractmethod
    def send_email(
        self,
        template_code: str,
        to: list[str],
        context: dict,
        attachments: list[dict] | None = None,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
    ) -> bool:
        ...
